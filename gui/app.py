"""Tkinter GUI for the flight search application."""

from __future__ import annotations

import logging
import tkinter as tk
import threading
import webbrowser
from collections.abc import Callable
from datetime import date, timedelta
from tkinter import filedialog, messagebox, ttk

from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg

from config import AppConfig, load_config, save_env_setting
from flight_api import FlightProviderError
from flight_api.provider_factory import SUPPORTED_PROVIDERS, create_flight_provider
from plotting.price_plot import create_price_history_figure
from services import (
    AutomaticCheckResult,
    AutomaticTrackingService,
    CHECK_INTERVAL_OPTIONS,
    NotificationService,
    SearchService,
    SearchValidationError,
    TrackingError,
    TrackingService,
    TrackedRouteStatus,
    export_price_history_to_csv,
)
from storage import (
    FlightOffer,
    PriceHistoryEntry,
    TrackedRoute,
    initialize_database,
)


LOGGER = logging.getLogger(__name__)


RESULT_COLUMNS = (
    ("airline", "Airline", 120),
    ("origin", "Origin", 80),
    ("destination", "Destination", 100),
    ("departure", "Departure", 150),
    ("arrival", "Arrival", 150),
    ("duration", "Duration", 90),
    ("stops", "Stops", 70),
    ("price", "Price", 90),
    ("currency", "Currency", 80),
)

TRACKING_COLUMNS = (
    ("id", "ID", 60),
    ("route", "Route", 130),
    ("departure", "Departure", 110),
    ("return", "Return", 110),
    ("target", "Target", 100),
    ("interval", "Interval", 120),
    ("alerts", "Alerts", 80),
    ("last_checked", "Last Checked", 150),
    ("current", "Current", 100),
    ("lowest", "Lowest", 100),
)

SETTINGS_ROWS = (
    ("Flight API Provider", "flight_api_provider"),
    ("Amadeus Credentials", "amadeus_credentials"),
    ("SerpApi Credentials", "serpapi_credentials"),
    ("Default Currency", "default_currency"),
    ("Default Origin", "default_origin"),
    ("Database Path", "database_path"),
    ("Amadeus Base URL", "amadeus_base_url"),
    ("SerpApi Base URL", "serpapi_base_url"),
)


def format_offer_row(offer: FlightOffer) -> tuple[str, ...]:
    return (
        offer.airline,
        offer.origin,
        offer.destination,
        offer.departure_time.strftime("%Y-%m-%d %H:%M"),
        offer.arrival_time.strftime("%Y-%m-%d %H:%M"),
        offer.duration,
        str(offer.number_of_stops),
        f"{offer.price:.2f}",
        offer.currency,
    )


def format_route_status_row(status: TrackedRouteStatus) -> tuple[str, ...]:
    route = status.route
    target = f"{route.max_price:.2f} {route.currency}" if route.max_price else ""
    current = (
        f"{status.current_price:.2f} {route.currency}" if status.current_price else ""
    )
    lowest = f"{status.lowest_price:.2f} {route.currency}" if status.lowest_price else ""
    return (
        str(route.id),
        f"{route.origin} -> {route.destination}",
        route.departure_date.isoformat(),
        route.return_date.isoformat() if route.return_date else "",
        target,
        AutomaticTrackingService.interval_label(route.check_interval_hours),
        "On" if route.notification_enabled else "Off",
        route.last_checked_at.strftime("%Y-%m-%d %H:%M")
        if route.last_checked_at
        else "",
        current,
        lowest,
    )


def format_price_history_message(entry: PriceHistoryEntry) -> str:
    return f"Current cheapest: {entry.price:.2f} {entry.currency} ({entry.airline})"


def settings_display_rows(config: AppConfig) -> list[tuple[str, str]]:
    values = {
        "flight_api_provider": config.flight_api_provider,
        "amadeus_credentials": (
            "Configured" if config.amadeus_credentials_configured else "Missing"
        ),
        "serpapi_credentials": (
            "Configured" if config.serpapi_credentials_configured else "Missing"
        ),
        "default_currency": config.default_currency,
        "default_origin": config.default_origin or "Not set",
        "database_path": str(config.database_path),
        "amadeus_base_url": config.amadeus_base_url,
        "serpapi_base_url": config.serpapi_base_url,
    }
    return [(label, values[key]) for label, key in SETTINGS_ROWS]


class DatePickerPopup(tk.Toplevel):
    def __init__(self, parent: tk.Widget, target_var: tk.StringVar) -> None:
        super().__init__(parent)
        self.title("Pick Date")
        self.resizable(False, False)
        self.target_var = target_var
        self.selected_date = self._initial_date(target_var.get())
        self.date_var = tk.StringVar(value=self.selected_date.isoformat())
        self._build()
        self.transient(parent.winfo_toplevel())
        self.grab_set()

    def _build(self) -> None:
        frame = ttk.Frame(self, padding=12)
        frame.pack(fill="both", expand=True)
        ttk.Entry(frame, textvariable=self.date_var, width=14).grid(
            row=0, column=0, columnspan=4, sticky="ew", pady=(0, 8)
        )
        ttk.Button(frame, text="-1d", command=lambda: self._shift(-1)).grid(
            row=1, column=0, padx=(0, 4)
        )
        ttk.Button(frame, text="Today", command=self._today).grid(
            row=1, column=1, padx=4
        )
        ttk.Button(frame, text="+1d", command=lambda: self._shift(1)).grid(
            row=1, column=2, padx=4
        )
        ttk.Button(frame, text="Use", command=self._apply).grid(
            row=1, column=3, padx=(4, 0)
        )

    def _shift(self, days: int) -> None:
        self.selected_date = self._initial_date(self.date_var.get()) + timedelta(
            days=days
        )
        self.date_var.set(self.selected_date.isoformat())

    def _today(self) -> None:
        self.selected_date = date.today()
        self.date_var.set(self.selected_date.isoformat())

    def _apply(self) -> None:
        self.target_var.set(self._initial_date(self.date_var.get()).isoformat())
        self.destroy()

    @staticmethod
    def _initial_date(value: str) -> date:
        try:
            return date.fromisoformat(value.strip())
        except ValueError:
            return date.today()


class SearchTab(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        search_service: SearchService,
        default_origin: str = "",
        default_currency: str = "EUR",
        on_save_route: Callable[[dict[str, str], FlightOffer], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=12)
        self.search_service = search_service
        self.on_save_route = on_save_route
        self.last_results: list[FlightOffer] = []
        self.last_search: dict[str, str] = {}

        self.origin_var = tk.StringVar(value=default_origin or "STR")
        self.destination_var = tk.StringVar(value="LIS")
        self.departure_date_var = tk.StringVar(value="2026-07-10")
        self.return_date_var = tk.StringVar()
        self.trip_type_var = tk.StringVar(value="one_way")
        self.max_price_var = tk.StringVar(value="150")
        self.currency_var = tk.StringVar(value=default_currency or "EUR")
        self.status_var = tk.StringVar()

        self._build()
        self._sync_return_date_state()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        for index in range(8):
            controls.columnconfigure(index, weight=1)

        ttk.Label(controls, text="Origin").grid(row=0, column=0, sticky="w")
        ttk.Entry(controls, textvariable=self.origin_var, width=12).grid(
            row=1, column=0, sticky="ew", padx=(0, 8)
        )

        ttk.Label(controls, text="Destination").grid(row=0, column=1, sticky="w")
        ttk.Entry(controls, textvariable=self.destination_var, width=12).grid(
            row=1, column=1, sticky="ew", padx=(0, 8)
        )

        ttk.Label(controls, text="Departure").grid(row=0, column=2, sticky="w")
        ttk.Entry(controls, textvariable=self.departure_date_var, width=14).grid(
            row=1, column=2, sticky="ew", padx=(0, 8)
        )
        ttk.Button(
            controls,
            text="Pick",
            command=lambda: DatePickerPopup(self, self.departure_date_var),
        ).grid(row=2, column=2, sticky="ew", padx=(0, 8), pady=(4, 0))

        ttk.Label(controls, text="Return").grid(row=0, column=3, sticky="w")
        self.return_entry = ttk.Entry(
            controls, textvariable=self.return_date_var, width=14
        )
        self.return_entry.grid(row=1, column=3, sticky="ew", padx=(0, 8))
        self.return_pick_button = ttk.Button(
            controls,
            text="Pick",
            command=lambda: DatePickerPopup(self, self.return_date_var),
        )
        self.return_pick_button.grid(row=2, column=3, sticky="ew", padx=(0, 8), pady=(4, 0))

        trip_frame = ttk.Frame(controls)
        trip_frame.grid(row=1, column=4, sticky="ew", padx=(0, 8))
        ttk.Radiobutton(
            trip_frame,
            text="One-way",
            variable=self.trip_type_var,
            value="one_way",
            command=self._sync_return_date_state,
        ).pack(side="left")
        ttk.Radiobutton(
            trip_frame,
            text="Round-trip",
            variable=self.trip_type_var,
            value="round_trip",
            command=self._sync_return_date_state,
        ).pack(side="left", padx=(8, 0))

        ttk.Label(controls, text="Max Price").grid(row=0, column=5, sticky="w")
        ttk.Entry(controls, textvariable=self.max_price_var, width=10).grid(
            row=1, column=5, sticky="ew", padx=(0, 8)
        )

        ttk.Label(controls, text="Currency").grid(row=0, column=6, sticky="w")
        ttk.Combobox(
            controls,
            textvariable=self.currency_var,
            values=("EUR", "USD", "GBP"),
            width=8,
            state="readonly",
        ).grid(row=1, column=6, sticky="ew", padx=(0, 8))

        self.search_button = ttk.Button(
            controls, text="Search", command=self._on_search
        )
        self.search_button.grid(row=1, column=7, sticky="ew")
        ttk.Label(
            controls,
            text="Airport hints: STR, BER, FRA, MUC",
        ).grid(row=2, column=0, columnspan=2, sticky="w", pady=(4, 0))

        self.results_table = ttk.Treeview(
            self,
            columns=[column_id for column_id, _, _ in RESULT_COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for column_id, heading, width in RESULT_COLUMNS:
            self.results_table.heading(column_id, text=heading)
            self.results_table.column(column_id, width=width, anchor="w")
        self.results_table.grid(row=1, column=0, sticky="nsew")
        self.results_table.bind("<<TreeviewSelect>>", self._on_result_selected)

        table_scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.results_table.yview
        )
        table_scrollbar.grid(row=1, column=1, sticky="ns")
        self.results_table.configure(yscrollcommand=table_scrollbar.set)

        actions = ttk.Frame(self)
        actions.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w"
        )
        self.save_button = ttk.Button(
            actions,
            text="Save Route",
            command=self._on_save_selected,
            state="disabled",
        )
        self.save_button.grid(row=0, column=1, sticky="e")
        self.open_button = ttk.Button(
            actions,
            text="Open Booking",
            command=self._on_open_booking,
            state="disabled",
        )
        self.open_button.grid(row=0, column=2, sticky="e", padx=(8, 0))

    def _sync_return_date_state(self) -> None:
        state = "normal" if self.trip_type_var.get() == "round_trip" else "disabled"
        self.return_entry.configure(state=state)
        self.return_pick_button.configure(state=state)

    def _on_search(self) -> None:
        values = self._current_search_values()
        self._set_search_running(True)

        def search_worker() -> None:
            try:
                offers = self.search_service.search(
                    origin=values["origin"],
                    destination=values["destination"],
                    departure_date=values["departure_date"],
                    return_date=values["return_date"],
                    is_round_trip=values["is_round_trip"] == "True",
                    max_price=values["max_price"],
                    currency=values["currency"],
                )
            except SearchValidationError as exc:
                self._finish_search_with_error("Invalid search", str(exc))
            except FlightProviderError as exc:
                self._finish_search_with_error("Flight API error", str(exc))
            except Exception as exc:
                LOGGER.exception("Unexpected search error")
                self._finish_search_with_error(
                    "Flight search error", f"Unexpected search error: {exc}"
                )
            else:
                self.after(0, lambda: self._finish_search_success(offers, values))

        threading.Thread(target=search_worker, daemon=True).start()

    def _set_search_running(self, is_running: bool) -> None:
        self.search_button.configure(state="disabled" if is_running else "normal")
        self.save_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        self.status_var.set("Searching..." if is_running else "")

    def _finish_search_success(
        self, offers: list[FlightOffer], search_values: dict[str, str]
    ) -> None:
        self.last_results = offers
        self.last_search = search_values
        self._populate_results(offers)
        self.search_button.configure(state="normal")
        self.status_var.set(f"{len(offers)} result(s)")

    def _finish_search_with_error(self, title: str, message: str) -> None:
        self.after(0, lambda: self._show_search_error(title, message))

    def _show_search_error(self, title: str, message: str) -> None:
        self.search_button.configure(state="normal")
        self.save_button.configure(state="disabled")
        self.open_button.configure(state="disabled")
        messagebox.showerror(title, message)
        self.status_var.set(message)

    def _populate_results(self, offers: list[FlightOffer]) -> None:
        for item_id in self.results_table.get_children():
            self.results_table.delete(item_id)
        for index, offer in enumerate(offers):
            self.results_table.insert("", "end", iid=str(index), values=format_offer_row(offer))
        self.save_button.configure(state="disabled")
        self.open_button.configure(state="disabled")

    def _on_result_selected(self, _event: tk.Event | None = None) -> None:
        offer = self.get_selected_offer()
        self.save_button.configure(state="normal" if offer else "disabled")
        self.open_button.configure(
            state="normal" if offer and offer.booking_url else "disabled"
        )

    def _on_save_selected(self) -> None:
        offer = self.get_selected_offer()
        if offer is None:
            self.status_var.set("Select a result first.")
            return
        if self.on_save_route is None:
            self.status_var.set("Tracking is not connected yet.")
            return
        try:
            self.on_save_route(self.last_search, offer)
        except TrackingError as exc:
            messagebox.showerror("Tracking error", str(exc))
            self.status_var.set(str(exc))
            return
        self.status_var.set("Route saved.")

    def _on_open_booking(self) -> None:
        offer = self.get_selected_offer()
        if offer is None or not offer.booking_url:
            self.status_var.set("No booking link available.")
            return
        webbrowser.open(offer.booking_url)
        LOGGER.info("Opened booking link for %s to %s", offer.origin, offer.destination)
        self.status_var.set("Booking link opened.")

    def get_selected_offer(self) -> FlightOffer | None:
        selection = self.results_table.selection()
        if not selection:
            return None
        index = int(selection[0])
        if index >= len(self.last_results):
            return None
        return self.last_results[index]

    def _current_search_values(self) -> dict[str, str]:
        return {
            "origin": self.origin_var.get().strip().upper(),
            "destination": self.destination_var.get().strip().upper(),
            "departure_date": self.departure_date_var.get().strip(),
            "return_date": self.return_date_var.get().strip(),
            "is_round_trip": str(self.trip_type_var.get() == "round_trip"),
            "max_price": self.max_price_var.get().strip(),
            "currency": self.currency_var.get().strip().upper(),
        }


class TrackingTab(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        tracking_service: TrackingService,
        automatic_tracking_service: AutomaticTrackingService,
        notification_service: NotificationService,
        on_routes_changed: Callable[[], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=12)
        self.tracking_service = tracking_service
        self.automatic_tracking_service = automatic_tracking_service
        self.notification_service = notification_service
        self.on_routes_changed = on_routes_changed
        self.interval_var = tk.StringVar(value="Manual only")
        self.notification_enabled_var = tk.BooleanVar(value=True)
        self.status_var = tk.StringVar()
        self._build()
        self.refresh()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(0, weight=1)

        self.routes_table = ttk.Treeview(
            self,
            columns=[column_id for column_id, _, _ in TRACKING_COLUMNS],
            show="headings",
            selectmode="browse",
        )
        for column_id, heading, width in TRACKING_COLUMNS:
            self.routes_table.heading(column_id, text=heading)
            self.routes_table.column(column_id, width=width, anchor="w")
        self.routes_table.grid(row=0, column=0, sticky="nsew")

        table_scrollbar = ttk.Scrollbar(
            self, orient="vertical", command=self.routes_table.yview
        )
        table_scrollbar.grid(row=0, column=1, sticky="ns")
        self.routes_table.configure(yscrollcommand=table_scrollbar.set)

        actions = ttk.Frame(self)
        actions.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(10, 0))
        actions.columnconfigure(0, weight=1)
        ttk.Label(actions, textvariable=self.status_var).grid(
            row=0, column=0, sticky="w"
        )
        ttk.Button(actions, text="Refresh", command=self.refresh).grid(
            row=0, column=1, padx=(8, 0)
        )
        self.check_button = ttk.Button(
            actions, text="Check Price Now", command=self._check_price
        )
        self.check_button.grid(row=0, column=2, padx=(8, 0))
        self.remove_button = ttk.Button(
            actions, text="Remove", command=self._remove_route
        )
        self.remove_button.grid(row=0, column=3, padx=(8, 0))
        self.interval_selector = ttk.Combobox(
            actions,
            textvariable=self.interval_var,
            values=tuple(CHECK_INTERVAL_OPTIONS),
            width=16,
            state="readonly",
        )
        self.interval_selector.grid(row=0, column=4, padx=(8, 0))
        ttk.Button(actions, text="Apply Interval", command=self._apply_interval).grid(
            row=0, column=5, padx=(8, 0)
        )
        ttk.Checkbutton(
            actions,
            text="Notify below target",
            variable=self.notification_enabled_var,
        ).grid(row=0, column=6, padx=(8, 0))
        ttk.Button(
            actions,
            text="Apply Alert",
            command=self._apply_notification_setting,
        ).grid(row=0, column=7, padx=(8, 0))
        ttk.Button(actions, text="Run Due Checks", command=self._run_due_checks).grid(
            row=0, column=8, padx=(8, 0)
        )

    def refresh(self) -> None:
        for item_id in self.routes_table.get_children():
            self.routes_table.delete(item_id)
        for status in self.tracking_service.list_route_statuses():
            route_id = status.route.id
            self.routes_table.insert(
                "", "end", iid=str(route_id), values=format_route_status_row(status)
            )

    def _selected_route_id(self) -> int | None:
        selection = self.routes_table.selection()
        if not selection:
            self.status_var.set("Select a tracked route first.")
            return None
        return int(selection[0])

    def _check_price(self) -> None:
        route_id = self._selected_route_id()
        if route_id is None:
            return
        self._set_check_running(True)

        def check_worker() -> None:
            try:
                entry = self.tracking_service.check_price_now(route_id)
            except TrackingError as exc:
                self._finish_check_with_error(str(exc))
            except Exception as exc:
                LOGGER.exception("Unexpected tracking error")
                self._finish_check_with_error(f"Unexpected tracking error: {exc}")
            else:
                self.after(0, lambda: self._finish_check_success(entry))

        threading.Thread(target=check_worker, daemon=True).start()

    def _remove_route(self) -> None:
        route_id = self._selected_route_id()
        if route_id is None:
            return
        self.tracking_service.remove_route(route_id)
        self.refresh()
        self._notify_routes_changed()
        self.status_var.set("Route removed.")

    def _apply_interval(self) -> None:
        route_id = self._selected_route_id()
        if route_id is None:
            return
        try:
            self.automatic_tracking_service.set_route_interval(
                route_id, self.interval_var.get()
            )
        except TrackingError as exc:
            messagebox.showerror("Tracking error", str(exc))
            self.status_var.set(str(exc))
            return
        self.refresh()
        self._notify_routes_changed()
        self.status_var.set("Tracking interval updated.")

    def _apply_notification_setting(self) -> None:
        route_id = self._selected_route_id()
        if route_id is None:
            return
        self.notification_service.set_route_notifications_enabled(
            route_id, self.notification_enabled_var.get()
        )
        self.refresh()
        self._notify_routes_changed()
        self.status_var.set("Notification setting updated.")

    def _run_due_checks(self) -> None:
        self._set_check_running(True)

        def due_check_worker() -> None:
            try:
                results = self.automatic_tracking_service.run_due_checks()
            except Exception as exc:
                LOGGER.exception("Unexpected automatic tracking error")
                self._finish_check_with_error(
                    f"Unexpected automatic tracking error: {exc}"
                )
            else:
                self.after(0, lambda: self._finish_due_checks(results))

        threading.Thread(target=due_check_worker, daemon=True).start()

    def _notify_routes_changed(self) -> None:
        if self.on_routes_changed:
            self.on_routes_changed()

    def _set_check_running(self, is_running: bool) -> None:
        state = "disabled" if is_running else "normal"
        self.check_button.configure(state=state)
        self.remove_button.configure(state=state)
        self.status_var.set("Checking price..." if is_running else "")

    def _finish_check_success(self, entry: PriceHistoryEntry) -> None:
        self._set_check_running(False)
        self.refresh()
        self._notify_routes_changed()
        self._show_notification_for_entry(entry)
        self.status_var.set(format_price_history_message(entry))

    def _finish_check_with_error(self, message: str) -> None:
        self.after(0, lambda: self._show_check_error(message))

    def _show_check_error(self, message: str) -> None:
        self._set_check_running(False)
        messagebox.showerror("Tracking error", message)
        self.status_var.set(message)

    def _finish_due_checks(self, results: list[AutomaticCheckResult]) -> None:
        self._set_check_running(False)
        self.refresh()
        self._notify_routes_changed()
        for result in results:
            if result.entry is not None:
                self._show_notification_for_entry(result.entry)
        checked_count = sum(1 for result in results if result.entry is not None)
        error_count = sum(1 for result in results if result.error)
        if error_count:
            self.status_var.set(
                f"{checked_count} route(s) checked, {error_count} error(s)."
            )
        else:
            self.status_var.set(f"{checked_count} due route(s) checked.")

    def _show_notification_for_entry(self, entry: PriceHistoryEntry) -> None:
        notification = self.notification_service.notification_for_entry(entry)
        if notification is not None:
            messagebox.showinfo("Target price reached", notification.message)


class PriceGraphTab(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        tracking_service: TrackingService,
    ) -> None:
        super().__init__(parent, padding=12)
        self.tracking_service = tracking_service
        self.route_var = tk.StringVar()
        self.status_var = tk.StringVar()
        self.route_options: dict[str, TrackedRoute] = {}
        self.canvas: FigureCanvasTkAgg | None = None
        self._build()
        self.refresh_routes()

    def _build(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        controls = ttk.Frame(self)
        controls.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        controls.columnconfigure(0, weight=1)

        self.route_selector = ttk.Combobox(
            controls,
            textvariable=self.route_var,
            state="readonly",
        )
        self.route_selector.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(controls, text="Refresh", command=self.refresh_routes).grid(
            row=0, column=1, padx=(0, 8)
        )
        ttk.Button(controls, text="Plot Price History", command=self._plot).grid(
            row=0, column=2
        )
        ttk.Button(controls, text="Export CSV", command=self._export_csv).grid(
            row=0, column=3, padx=(8, 0)
        )

        self.plot_container = ttk.Frame(self)
        self.plot_container.grid(row=1, column=0, sticky="nsew")
        ttk.Label(self, textvariable=self.status_var).grid(
            row=2, column=0, sticky="w", pady=(10, 0)
        )

    def refresh_routes(self) -> None:
        statuses = self.tracking_service.list_route_statuses()
        self.route_options = {
            self._route_label(status): status.route for status in statuses
        }
        labels = list(self.route_options)
        self.route_selector.configure(values=labels)
        if self.route_var.get() not in self.route_options:
            self.route_var.set(labels[0] if labels else "")

    def _plot(self) -> None:
        route = self.route_options.get(self.route_var.get())
        if route is None:
            self.status_var.set("Select a tracked route first.")
            return

        figure = create_price_history_figure(self.tracking_service.database, route)
        if self.canvas is not None:
            self.canvas.get_tk_widget().destroy()
        self.canvas = FigureCanvasTkAgg(figure, master=self.plot_container)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill="both", expand=True)
        self.status_var.set("Price history plotted.")

    def _export_csv(self) -> None:
        route = self.route_options.get(self.route_var.get())
        if route is None or route.id is None:
            self.status_var.set("Select a tracked route first.")
            return
        output_path = filedialog.asksaveasfilename(
            defaultextension=".csv",
            filetypes=(("CSV files", "*.csv"), ("All files", "*.*")),
            initialfile=f"{route.origin}_{route.destination}_price_history.csv",
        )
        if not output_path:
            return
        export_price_history_to_csv(
            self.tracking_service.database,
            route.id,
            output_path,
        )
        LOGGER.info("Exported price history for route %s to %s", route.id, output_path)
        self.status_var.set("Price history exported.")

    @staticmethod
    def _route_label(status: TrackedRouteStatus) -> str:
        route = status.route
        return f"{route.id}: {route.origin} -> {route.destination} ({route.departure_date})"


class SettingsTab(ttk.Frame):
    def __init__(self, parent: tk.Widget, config: AppConfig) -> None:
        super().__init__(parent, padding=12)
        self.config = config
        self.provider_var = tk.StringVar(value=config.flight_api_provider)
        self.status_var = tk.StringVar()
        self._build()

    def _build(self) -> None:
        for row_index, (label, value) in enumerate(settings_display_rows(self.config)):
            ttk.Label(self, text=label).grid(
                row=row_index, column=0, sticky="w", padx=(0, 12), pady=4
            )
            ttk.Label(self, text=value).grid(
                row=row_index, column=1, sticky="w", pady=4
            )
        provider_row = len(SETTINGS_ROWS)
        ttk.Label(self, text="Change Provider").grid(
            row=provider_row, column=0, sticky="w", padx=(0, 12), pady=(16, 4)
        )
        ttk.Combobox(
            self,
            textvariable=self.provider_var,
            values=SUPPORTED_PROVIDERS,
            state="readonly",
            width=28,
        ).grid(row=provider_row, column=1, sticky="w", pady=(16, 4))
        ttk.Button(
            self,
            text="Save Provider",
            command=self._save_provider,
        ).grid(row=provider_row, column=2, sticky="w", padx=(12, 0), pady=(16, 4))
        ttk.Label(self, textvariable=self.status_var).grid(
            row=provider_row + 1, column=0, columnspan=3, sticky="w", pady=(4, 0)
        )
        ttk.Label(
            self,
            text="API credentials are loaded from environment variables or a local .env file.",
        ).grid(row=provider_row + 2, column=0, columnspan=3, sticky="w", pady=(16, 0))

    def _save_provider(self) -> None:
        provider = self.provider_var.get()
        save_env_setting("FLIGHT_API_PROVIDER", provider)
        self.status_var.set("Provider saved. Restart the app to use it.")
        LOGGER.info("Saved flight provider setting: %s", provider)


class FlightSearchApp(tk.Tk):
    def __init__(self, config: AppConfig | None = None) -> None:
        super().__init__()
        self.title("Flight Search")
        self.geometry("1080x640")
        self.minsize(900, 520)

        self.config = config or load_config()
        database = initialize_database(self.config.database_path)
        search_service = SearchService(create_flight_provider(self.config))
        tracking_service = TrackingService(database, search_service)
        automatic_tracking_service = AutomaticTrackingService(tracking_service)
        notification_service = NotificationService(database)

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.search_tab = SearchTab(
            notebook,
            search_service,
            default_origin=self.config.default_origin,
            default_currency=self.config.default_currency,
            on_save_route=self._save_route,
        )
        self.price_graph_tab = PriceGraphTab(notebook, tracking_service)
        self.tracking_tab = TrackingTab(
            notebook,
            tracking_service,
            automatic_tracking_service,
            notification_service,
            self.price_graph_tab.refresh_routes,
        )
        notebook.add(self.search_tab, text="Search")
        notebook.add(self.tracking_tab, text="Tracking")
        notebook.add(self.price_graph_tab, text="Price Graph")
        notebook.add(SettingsTab(notebook, self.config), text="Settings")

    def _save_route(self, search_values: dict[str, str], offer: FlightOffer) -> None:
        self.tracking_tab.tracking_service.add_route_from_search(search_values, offer)
        self.tracking_tab.refresh()
        self.price_graph_tab.refresh_routes()


def run_app() -> None:
    app = FlightSearchApp()
    app.mainloop()
