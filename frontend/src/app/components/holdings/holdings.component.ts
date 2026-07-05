import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { StockService, StockHolding, MarketDirectoryEntry } from '../../services/stock.service';
import { StockModalComponent } from '../stock-modal/stock-modal.component';

@Component({
  selector: 'app-holdings',
  standalone: true,
  imports: [CommonModule, FormsModule, StockModalComponent],
  templateUrl: './holdings.component.html',
  styleUrls: ['./holdings.component.css']
})
export class HoldingsComponent implements OnInit {
  holdings: StockHolding[] = [];
  directory: MarketDirectoryEntry[] = [];
  isLoading = true;
  showBuyForm = false;

  // Modal state
  modalTicker: string | null = null;
  modalHolding: StockHolding | null = null;

  openModal(h: StockHolding): void { this.modalTicker = h.ticker; this.modalHolding = h; }
  closeModal(): void { this.modalTicker = null; this.modalHolding = null; }

  // Form fields
  buyTicker = '';
  buyQuantity: number | null = null;
  buyPrice: number | null = null;
  buyError = '';
  buySuccess = '';
  isSubmitting = false;

  // Autocomplete
  autocompleteResults: MarketDirectoryEntry[] = [];
  showAutocomplete = false;

  constructor(
    private stockService: StockService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadData();
  }

  loadData(): void {
    this.isLoading = true;
    this.stockService.getHoldings().subscribe({
      next: (data) => {
        this.holdings = data;
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => { this.isLoading = false; this.cdr.detectChanges(); }
    });
    this.stockService.getDirectory().subscribe({
      next: (data) => { this.directory = data; this.cdr.detectChanges(); },
      error: () => {}
    });
  }

  // Totals
  get totalInvested(): number {
    return this.holdings.reduce((s, h) => s + h.quantity * h.average_buy_price, 0);
  }

  getCurrentPrice(ticker: string): number {
    const entry = this.directory.find(d => d.ticker === ticker);
    return entry?.current_price ?? 0;
  }

  get totalCurrentValue(): number {
    return this.holdings.reduce((s, h) => {
      const cp = this.getCurrentPrice(h.ticker);
      return s + (cp > 0 ? h.quantity * cp : h.quantity * h.average_buy_price);
    }, 0);
  }

  get totalPnL(): number { return this.totalCurrentValue - this.totalInvested; }
  get totalPnLPct(): number { return this.totalInvested > 0 ? (this.totalPnL / this.totalInvested) * 100 : 0; }

  holdingPnL(h: StockHolding): number {
    const cp = this.getCurrentPrice(h.ticker);
    if (cp <= 0) return 0;
    return (cp - h.average_buy_price) * h.quantity;
  }

  holdingPnLPct(h: StockHolding): number {
    return h.average_buy_price > 0 ? ((this.getCurrentPrice(h.ticker) - h.average_buy_price) / h.average_buy_price) * 100 : 0;
  }

  allocationPct(h: StockHolding): number {
    const val = h.quantity * (this.getCurrentPrice(h.ticker) || h.average_buy_price);
    return this.totalCurrentValue > 0 ? (val / this.totalCurrentValue) * 100 : 0;
  }

  // SVG donut helpers
  get donutSegments(): { ticker: string; color: string; dashArray: string; dashOffset: string }[] {
    const colors = ['#00E699','#6366f1','#f59e0b','#ef4444','#22d3ee','#a78bfa','#34d399','#fb923c','#e879f9','#38bdf8'];
    const circumference = 2 * Math.PI * 40;
    let cumulative = 0;
    return this.holdings.map((h, i) => {
      const pct = this.allocationPct(h) / 100;
      const dash = circumference * pct;
      const gap = circumference - dash;
      const offset = circumference - cumulative * circumference;
      cumulative += pct;
      return {
        ticker: h.ticker,
        color: colors[i % colors.length],
        dashArray: `${dash.toFixed(2)} ${gap.toFixed(2)}`,
        dashOffset: offset.toFixed(2)
      };
    });
  }

  // Buy form autocomplete
  onBuyTickerInput(): void {
    const q = this.buyTicker.trim().toLowerCase();
    if (q.length < 1) { this.autocompleteResults = []; this.showAutocomplete = false; return; }
    this.autocompleteResults = this.directory
      .filter(d => d.ticker.toLowerCase().includes(q) || (d.company_name||'').toLowerCase().includes(q))
      .slice(0, 6);
    this.showAutocomplete = this.autocompleteResults.length > 0;
  }

  selectAutocomplete(entry: MarketDirectoryEntry): void {
    this.buyTicker = entry.ticker;
    if (!this.buyPrice) this.buyPrice = entry.current_price;
    this.showAutocomplete = false;
    this.cdr.detectChanges();
  }

  submitBuy(): void {
    if (!this.buyTicker || !this.buyQuantity || !this.buyPrice) {
      this.buyError = 'All fields are required.'; return;
    }
    this.isSubmitting = true;
    this.buyError = '';
    this.stockService.addHolding(this.buyTicker.toUpperCase(), this.buyQuantity, this.buyPrice).subscribe({
      next: () => {
        this.isSubmitting = false;
        this.showBuyForm = false;
        this.buyTicker = ''; this.buyQuantity = null; this.buyPrice = null;
        this.buySuccess = 'Holding recorded successfully!';
        setTimeout(() => { this.buySuccess = ''; this.cdr.detectChanges(); }, 3000);
        this.loadData();
      },
      error: (err) => {
        this.isSubmitting = false;
        this.buyError = err.error?.detail || 'Failed to record holding.';
        this.cdr.detectChanges();
      }
    });
  }

  deleteHolding(id: string): void {
    this.stockService.deleteHolding(id).subscribe({
      next: () => { this.holdings = this.holdings.filter(h => h.id !== id); this.cdr.detectChanges(); },
      error: () => {}
    });
  }
}
