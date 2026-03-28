"""Full Indian equity/options trading cost model."""

from typing import Dict


class IndianCostModel:
    """Full Indian equity/options trading cost model.

    Covers brokerage, STT, exchange transaction charges, GST, SEBI charges,
    and stamp duty for equity intraday, equity delivery, and options trades.
    Rates default to Zerodha's fee schedule.
    """

    def __init__(self, broker: str = "zerodha"):
        self.broker = broker

        # --- Zerodha-specific rates ---
        # Equity intraday (MIS)
        self.eq_intraday_brokerage_pct = 0.0003  # 0.03%
        self.brokerage_cap = 20.0  # Rs 20 cap per executed order

        # Equity delivery (CNC)
        self.eq_delivery_brokerage_pct = 0.0  # Zero brokerage for delivery

        # Options
        self.opt_brokerage_flat = 20.0  # Rs 20 flat per order

        # STT (Securities Transaction Tax)
        self.stt_eq_intraday_sell_pct = 0.00025  # 0.025% on sell side
        self.stt_eq_delivery_pct = 0.001  # 0.1% on both buy and sell
        self.stt_opt_sell_pct = 0.000625  # 0.0625% on sell side (on premium)

        # Exchange transaction charges
        self.nse_txn_eq_pct = 0.0000345  # 0.00345%
        self.bse_txn_eq_pct = 0.0000375  # 0.00375%
        self.nse_txn_opt_pct = 0.0005  # 0.05%

        # GST
        self.gst_pct = 0.18  # 18% on (brokerage + transaction charges)

        # SEBI charges
        self.sebi_per_crore = 10.0  # Rs 10 per crore of turnover

        # Stamp duty
        self.stamp_duty_pct = 0.00003  # 0.003% on buy side only

        # Default exchange
        self.exchange = "NSE"

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def calculate_costs(
        self,
        price: float,
        quantity: int,
        side: str,
        instrument_type: str = "EQ",
    ) -> Dict[str, float]:
        """Calculate all costs for a single-leg trade.

        Args:
            price: Trade price per unit.
            quantity: Number of shares / lots.
            side: 'buy' or 'sell'.
            instrument_type: 'EQ' (equity intraday), 'EQ_DEL' (delivery),
                             or 'OPT' (options).

        Returns:
            Dict with itemised breakdown and 'total' key.
        """
        instrument_type = instrument_type.upper()
        if instrument_type == "EQ":
            return self.calculate_equity_intraday_costs(price, quantity, side)
        elif instrument_type == "EQ_DEL":
            return self.calculate_equity_delivery_costs(price, quantity, side)
        elif instrument_type == "OPT":
            return self.calculate_option_costs(price, quantity, 1, side)
        else:
            raise ValueError(f"Unknown instrument_type: {instrument_type}")

    def calculate_equity_intraday_costs(
        self, price: float, qty: int, side: str
    ) -> Dict[str, float]:
        """Cost breakdown for an equity intraday (MIS) trade."""
        side = side.lower()
        turnover = price * qty

        # Brokerage: 0.03% or Rs 20, whichever is lower
        brokerage = min(turnover * self.eq_intraday_brokerage_pct, self.brokerage_cap)

        # STT: 0.025% on sell side only
        stt = turnover * self.stt_eq_intraday_sell_pct if side == "sell" else 0.0

        # Transaction charges (NSE default)
        txn_pct = (
            self.nse_txn_eq_pct
            if self.exchange == "NSE"
            else self.bse_txn_eq_pct
        )
        txn_charges = turnover * txn_pct

        # GST: 18% on (brokerage + transaction charges)
        gst = (brokerage + txn_charges) * self.gst_pct

        # SEBI charges: Rs 10 per crore
        sebi = turnover * self.sebi_per_crore / 1e7

        # Stamp duty: 0.003% on buy side only
        stamp = turnover * self.stamp_duty_pct if side == "buy" else 0.0

        total = brokerage + stt + txn_charges + gst + sebi + stamp

        return {
            "turnover": round(turnover, 2),
            "brokerage": round(brokerage, 2),
            "stt": round(stt, 2),
            "txn_charges": round(txn_charges, 4),
            "gst": round(gst, 4),
            "sebi": round(sebi, 4),
            "stamp_duty": round(stamp, 4),
            "total": round(total, 4),
        }

    def calculate_equity_delivery_costs(
        self, price: float, qty: int, side: str
    ) -> Dict[str, float]:
        """Cost breakdown for an equity delivery (CNC) trade."""
        side = side.lower()
        turnover = price * qty

        # Brokerage: zero for delivery on Zerodha
        brokerage = 0.0

        # STT: 0.1% on both sides
        stt = turnover * self.stt_eq_delivery_pct

        # Transaction charges
        txn_pct = (
            self.nse_txn_eq_pct
            if self.exchange == "NSE"
            else self.bse_txn_eq_pct
        )
        txn_charges = turnover * txn_pct

        # GST
        gst = (brokerage + txn_charges) * self.gst_pct

        # SEBI
        sebi = turnover * self.sebi_per_crore / 1e7

        # Stamp duty on buy side only
        stamp = turnover * self.stamp_duty_pct if side == "buy" else 0.0

        total = brokerage + stt + txn_charges + gst + sebi + stamp

        return {
            "turnover": round(turnover, 2),
            "brokerage": round(brokerage, 2),
            "stt": round(stt, 2),
            "txn_charges": round(txn_charges, 4),
            "gst": round(gst, 4),
            "sebi": round(sebi, 4),
            "stamp_duty": round(stamp, 4),
            "total": round(total, 4),
        }

    def calculate_option_costs(
        self,
        premium: float,
        qty: int,
        lot_size: int,
        side: str,
    ) -> Dict[str, float]:
        """Cost breakdown for an options trade.

        Args:
            premium: Option premium per unit.
            qty: Number of lots.
            lot_size: Units per lot.
            side: 'buy' or 'sell'.
        """
        side = side.lower()
        total_units = qty * lot_size
        turnover = premium * total_units

        # Brokerage: Rs 20 flat per order
        brokerage = self.opt_brokerage_flat

        # STT: 0.0625% on sell side (on premium value)
        stt = turnover * self.stt_opt_sell_pct if side == "sell" else 0.0

        # Transaction charges: NSE 0.05%
        txn_charges = turnover * self.nse_txn_opt_pct

        # GST
        gst = (brokerage + txn_charges) * self.gst_pct

        # SEBI
        sebi = turnover * self.sebi_per_crore / 1e7

        # Stamp duty on buy side only
        stamp = turnover * self.stamp_duty_pct if side == "buy" else 0.0

        total = brokerage + stt + txn_charges + gst + sebi + stamp

        return {
            "turnover": round(turnover, 2),
            "brokerage": round(brokerage, 2),
            "stt": round(stt, 2),
            "txn_charges": round(txn_charges, 4),
            "gst": round(gst, 4),
            "sebi": round(sebi, 4),
            "stamp_duty": round(stamp, 4),
            "total": round(total, 4),
        }

    def total_round_trip_cost(
        self,
        entry_price: float,
        exit_price: float,
        qty: int,
        instrument_type: str = "EQ",
        lot_size: int = 1,
    ) -> Dict[str, float]:
        """Full buy + sell cost for a round-trip trade.

        Returns a dict with per-leg breakdowns and combined total.
        """
        instrument_type = instrument_type.upper()

        if instrument_type == "OPT":
            buy_costs = self.calculate_option_costs(entry_price, qty, lot_size, "buy")
            sell_costs = self.calculate_option_costs(exit_price, qty, lot_size, "sell")
        elif instrument_type == "EQ_DEL":
            buy_costs = self.calculate_equity_delivery_costs(entry_price, qty, "buy")
            sell_costs = self.calculate_equity_delivery_costs(exit_price, qty, "sell")
        else:
            # Default: equity intraday
            buy_costs = self.calculate_equity_intraday_costs(entry_price, qty, "buy")
            sell_costs = self.calculate_equity_intraday_costs(exit_price, qty, "sell")

        total = buy_costs["total"] + sell_costs["total"]

        return {
            "buy_leg": buy_costs,
            "sell_leg": sell_costs,
            "total": round(total, 4),
        }

    def cost_as_pct(
        self,
        entry_price: float,
        exit_price: float,
        qty: int,
        instrument_type: str = "EQ",
        lot_size: int = 1,
    ) -> float:
        """Return total round-trip cost as a percentage of turnover.

        Turnover = (entry_price + exit_price) * qty [* lot_size for options].
        """
        rt = self.total_round_trip_cost(
            entry_price, exit_price, qty, instrument_type, lot_size
        )
        units = qty * lot_size if instrument_type.upper() == "OPT" else qty
        turnover = (entry_price + exit_price) * units
        if turnover == 0:
            return 0.0
        return round(rt["total"] / turnover * 100, 6)
