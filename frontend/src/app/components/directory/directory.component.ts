import { Component, OnInit, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { StockService, MarketDirectoryEntry } from '../../services/stock.service';
import { Router } from '@angular/router';
import { StockModalComponent } from '../stock-modal/stock-modal.component';

@Component({
  selector: 'app-directory',
  standalone: true,
  imports: [CommonModule, FormsModule, StockModalComponent],
  templateUrl: './directory.component.html',
  styleUrls: ['./directory.component.css']
})
export class DirectoryComponent implements OnInit {
  allStocks: MarketDirectoryEntry[] = [];
  filtered: MarketDirectoryEntry[] = [];
  searchQuery: string = '';
  isLoading: boolean = true;
  sortKey: 'ticker' | 'current_price' | 'change_percentage' | 'volume' = 'ticker';
  sortAsc: boolean = true;

  // Modal state
  modalTicker: string | null = null;
  openModal(ticker: string): void { this.modalTicker = ticker; }
  closeModal(): void { this.modalTicker = null; }

  constructor(
    private stockService: StockService,
    private cdr: ChangeDetectorRef,
    private router: Router
  ) {}

  ngOnInit(): void {
    this.stockService.getDirectory().subscribe({
      next: (data) => {
        this.allStocks = data;
        this.applyFilter();
        this.isLoading = false;
        this.cdr.detectChanges();
      },
      error: () => { this.isLoading = false; this.cdr.detectChanges(); }
    });
  }

  applyFilter(): void {
    const q = this.searchQuery.toLowerCase();
    let results = q
      ? this.allStocks.filter(s =>
          s.ticker.toLowerCase().includes(q) ||
          (s.company_name || '').toLowerCase().includes(q)
        )
      : [...this.allStocks];

    results.sort((a, b) => {
      const av = a[this.sortKey];
      const bv = b[this.sortKey];
      if (typeof av === 'string' && typeof bv === 'string')
        return this.sortAsc ? av.localeCompare(bv) : bv.localeCompare(av);
      return this.sortAsc ? (av as number) - (bv as number) : (bv as number) - (av as number);
    });

    this.filtered = results;
  }

  setSort(key: typeof this.sortKey): void {
    if (this.sortKey === key) {
      this.sortAsc = !this.sortAsc;
    } else {
      this.sortKey = key;
      this.sortAsc = key === 'ticker';
    }
    this.applyFilter();
  }

  goToWatchlist(ticker: string): void {
    this.router.navigate(['/watchlist'], { queryParams: { ticker } });
  }

  get gainers(): MarketDirectoryEntry[] {
    return [...this.allStocks].sort((a, b) => b.change_percentage - a.change_percentage).slice(0, 5);
  }

  get losers(): MarketDirectoryEntry[] {
    return [...this.allStocks].sort((a, b) => a.change_percentage - b.change_percentage).slice(0, 5);
  }
}
