"""Tkinter GUI for the flight search application."""

from __future__ import annotations

import tkinter as tk
from collections.abc import Callable
from tkinter import messagebox, ttk

from flight_api import MockFlightProvider
from services import SearchService, SearchValidationError
from storage import FlightOffer


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


class SearchTab(ttk.Frame):
    def __init__(
        self,
        parent: tk.Widget,
        search_service: SearchService,
        on_save_route: Callable[[dict[str, str], FlightOffer], None] | None = None,
    ) -> None:
        super().__init__(parent, padding=12)
        self.search_service = search_service
        self.on_save_route = on_save_route
        self.last_results: list[FlightOffer] = []
        self.last_search: dict[str, str] = {}

        self.origin_var = tk.StringVar(value="STR")
        self.destination_var = tk.StringVar(value="LIS")
        self.departure_date_var = tk.StringVar(value="2026-07-10")
        self.return_date_var = tk.StringVar()
        self.trip_type_var = tk.StringVar(value="one_way")
        self.max_price_var = tk.StringVar(value="150")
        self.currency_var = tk.StringVar(value="EUR")
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

        ttk.Label(controls, text="Return").grid(row=0, column=3, sticky="w")
        self.return_entry = ttk.Entry(
            controls, textvariable=self.return_date_var, width=14
        )
        self.return_entry.grid(row=1, column=3, sticky="ew", padx=(0, 8))

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

        ttk.Button(controls, text="Search", command=self._on_search).grid(
            row=1, column=7, sticky="ew"
        )

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

    def _sync_return_date_state(self) -> None:
        state = "normal" if self.trip_type_var.get() == "round_trip" else "disabled"
        self.return_entry.configure(state=state)

    def _on_search(self) -> None:
        self.status_var.set("")
        try:
            offers = self.search_service.search(
                origin=self.origin_var.get(),
                destination=self.destination_var.get(),
                departure_date=self.departure_date_var.get(),
                return_date=self.return_date_var.get(),
                is_round_trip=self.trip_type_var.get() == "round_trip",
                max_price=self.max_price_var.get(),
                currency=self.currency_var.get(),
            )
        except SearchValidationError as exc:
            messagebox.showerror("Invalid search", str(exc))
            self.status_var.set(str(exc))
            return

        self.last_results = offers
        self.last_search = self._current_search_values()
        self._populate_results(offers)
        self.status_var.set(f"{len(offers)} result(s)")

    def _populate_results(self, offers: list[FlightOffer]) -> None:
        for item_id in self.results_table.get_children():
            self.results_table.delete(item_id)
        for index, offer in enumerate(offers):
            self.results_table.insert("", "end", iid=str(index), values=format_offer_row(offer))
        self.save_button.configure(state="disabled")

    def _on_result_selected(self, _event: tk.Event | None = None) -> None:
        state = "normal" if self.get_selected_offer() else "disabled"
        self.save_button.configure(state=state)

    def _on_save_selected(self) -> None:
        offer = self.get_selected_offer()
        if offer is None:
            self.status_var.set("Select a result first.")
            return
        if self.on_save_route is None:
            self.status_var.set("Tracking is not connected yet.")
            return
        self.on_save_route(self.last_search, offer)

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


class FlightSearchApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Flight Search")
        self.geometry("1080x640")
        self.minsize(900, 520)

        search_service = SearchService(MockFlightProvider())

        notebook = ttk.Notebook(self)
        notebook.pack(fill="both", expand=True)

        self.search_tab = SearchTab(notebook, search_service)
        notebook.add(self.search_tab, text="Search")
        notebook.add(self._simple_tab(notebook, "Tracking"), text="Tracking")
        notebook.add(self._simple_tab(notebook, "Price Graph"), text="Price Graph")
        notebook.add(self._simple_tab(notebook, "Settings"), text="Settings")

    @staticmethod
    def _simple_tab(parent: tk.Widget, label: str) -> ttk.Frame:
        frame = ttk.Frame(parent, padding=12)
        ttk.Label(frame, text=label).pack(anchor="nw")
        return frame


def run_app() -> None:
    app = FlightSearchApp()
    app.mainloop()
