import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { StockService, StockWatchlistResponse, MarketDirectoryEntry } from '../../services/stock.service';
import { StockDetailComponent } from '../stock-detail/stock-detail.component';
import { StockModalComponent } from '../stock-modal/stock-modal.component';

@Component({
  selector: 'app-dashboard',
  standalone: true,
  imports: [CommonModule, FormsModule, StockDetailComponent, StockModalComponent],
  templateUrl: './dashboard.component.html',
  styleUrls: ['./dashboard.component.css']
})
export class DashboardComponent implements OnInit {
  stocks: StockWatchlistResponse[] = [];
  selectedStock: StockWatchlistResponse | null = null;

  newTicker: string = '';
  selectedModel: string = 'gemini-2.5-flash';
  isAdding: boolean = false;
  errorMessage: string = '';
  successMessage: string = '';

  // Autocomplete state
  directory: MarketDirectoryEntry[] = [];
  autocompleteResults: MarketDirectoryEntry[] = [];
  showAutocomplete: boolean = false;

  // Modal state
  modalTicker: string | null = null;

  constructor(
    private stockService: StockService,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnInit(): void {
    this.loadStocks();
    // Fetch the cached directory for autocomplete
    this.stockService.getDirectory().subscribe({
      next: (data) => { this.directory = data; this.cdr.detectChanges(); },
      error: () => {}
    });
  }

  loadStocks(): void {
    this.stockService.getStocks().subscribe({
      next: (data) => {
        this.stocks = data;
        if (this.selectedStock) {
          const updated = data.find(s => s.id === this.selectedStock!.id);
          this.selectedStock = updated || null;
        } else if (data.length > 0) {
          this.selectedStock = data[0];
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to load watchlist:', err);
        this.errorMessage = 'Could not establish connection to the backend database.';
        this.cdr.detectChanges();
      }
    });
  }

  onTickerInput(): void {
    const q = this.newTicker.trim().toLowerCase();
    if (q.length < 1) {
      this.autocompleteResults = [];
      this.showAutocomplete = false;
      return;
    }
    this.autocompleteResults = this.directory
      .filter(d =>
        d.ticker.toLowerCase().includes(q) ||
        (d.company_name || '').toLowerCase().includes(q)
      )
      .slice(0, 8);
    this.showAutocomplete = this.autocompleteResults.length > 0;
  }

  selectAutocomplete(entry: MarketDirectoryEntry): void {
    this.newTicker = entry.ticker;
    this.autocompleteResults = [];
    this.showAutocomplete = false;
    this.cdr.detectChanges();
  }

  closeAutocomplete(): void {
    setTimeout(() => { this.showAutocomplete = false; this.cdr.detectChanges(); }, 150);
  }

  selectStock(stock: StockWatchlistResponse): void {
    this.selectedStock = stock;
  }

  openModal(ticker: string): void { this.modalTicker = ticker; }
  closeModal(): void { this.modalTicker = null; }

  addStock(): void {
    const tickerToAdd = this.newTicker.trim().toUpperCase();
    if (!tickerToAdd) return;

    console.log('FRONTEND addStock() triggered for ticker:', tickerToAdd);
    this.isAdding = true;
    this.showAutocomplete = false;
    this.errorMessage = '';
    this.successMessage = '';

    this.stockService.addStock(tickerToAdd, this.selectedModel).subscribe({
      next: (newStock) => {
        try {
          console.log('FRONTEND addStock() next callback fired with payload:', newStock);
          this.stocks.push(newStock);
          this.selectedStock = newStock;
          this.newTicker = '';
          this.isAdding = false;
          this.successMessage = `Successfully validated and added ${tickerToAdd}.`;
          setTimeout(() => this.successMessage = '', 4000);
          console.log('FRONTEND addStock() next callback finished successfully!');
        } catch (ex: any) {
          console.error('FRONTEND addStock() next callback crashed with exception:', ex.message, ex.stack);
        } finally {
          this.cdr.detectChanges();
        }
      },
      error: (err) => {
        console.error('FRONTEND addStock() error callback fired with error:', err);
        this.isAdding = false;
        this.errorMessage = err.error?.detail || `Failed to validate and fetch data for ${tickerToAdd}.`;
        setTimeout(() => this.errorMessage = '', 5000);
        this.cdr.detectChanges();
      }
    });
  }

  handleDelete(stockId: string): void {
    this.stockService.deleteStock(stockId).subscribe({
      next: () => {
        this.stocks = this.stocks.filter(s => s.id !== stockId);
        if (this.selectedStock?.id === stockId) {
          this.selectedStock = this.stocks.length > 0 ? this.stocks[0] : null;
        }
        this.cdr.detectChanges();
      },
      error: (err) => {
        console.error('Failed to delete stock:', err);
        this.cdr.detectChanges();
      }
    });
  }

  handleReportUpdate(updatedReport: any): void {
    if (this.selectedStock) {
      this.selectedStock.latest_report = updatedReport;
      this.loadStocks();
    }
  }

  // Sparkline coordinates calculator
  getSparklinePath(prices: number[] | undefined): string {
    if (!prices || prices.length < 2) return 'M 0 15 L 100 15';
    const min = Math.min(...prices);
    const max = Math.max(...prices);
    const range = max - min || 1;
    return prices
      .map((price, index) => {
        const x = (index / (prices.length - 1)) * 100;
        const y = 30 - ((price - min) / range) * 24 - 3;
        return `${index === 0 ? 'M' : 'L'} ${x.toFixed(1)} ${y.toFixed(1)}`;
      })
      .join(' ');
  }

  getSparklineColor(prices: number[] | undefined): string {
    if (!prices || prices.length < 2) return '#8E95A5';
    return prices[prices.length - 1] >= prices[0] ? '#00E699' : '#FF4D4D';
  }

  get52WeekPosition(stock: StockWatchlistResponse): number {
    const metrics = stock.latest_metrics;
    if (!metrics) return 0;
    const pos = ((metrics.current_price - metrics.fifty_two_week_low) / (metrics.fifty_two_week_high - metrics.fifty_two_week_low || 1)) * 100;
    return Math.min(Math.max(pos, 0), 100);
  }
}
