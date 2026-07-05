import { Component, Input, Output, EventEmitter, OnChanges, SimpleChanges, ChangeDetectorRef } from '@angular/core';
import { CommonModule } from '@angular/common';
import { DomSanitizer, SafeHtml } from '@angular/platform-browser';
import { marked } from 'marked';
import { StockWatchlistResponse, StockService, GeminiAnalysisReport } from '../../services/stock.service';

@Component({
  selector: 'app-stock-detail',
  standalone: true,
  imports: [CommonModule],
  templateUrl: './stock-detail.component.html',
  styleUrls: ['./stock-detail.component.css']
})
export class StockDetailComponent implements OnChanges {
  @Input() stock: StockWatchlistResponse | null = null;
  @Input() selectedModel: string = 'gemini-2.5-flash';
  @Output() onAnalyze = new EventEmitter<GeminiAnalysisReport>();
  @Output() onDelete = new EventEmitter<{ id: string }>();

  isAnalyzing: boolean = false;
  errorMessage: string = '';
  reportHtml: SafeHtml = '';

  constructor(
    private stockService: StockService,
    private sanitizer: DomSanitizer,
    private cdr: ChangeDetectorRef
  ) {}

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['stock']) {
      this.errorMessage = '';
      this.renderReport();
    }
  }

  renderReport(): void {
    if (this.stock?.latest_report?.analysis_report) {
      try {
        const rawHtml = marked.parse(this.stock.latest_report.analysis_report) as string;
        this.reportHtml = this.sanitizer.bypassSecurityTrustHtml(rawHtml);
      } catch (err) {
        console.error('Markdown rendering error:', err);
        this.reportHtml = this.sanitizer.bypassSecurityTrustHtml(
          `<p class="text-crimsondanger font-mono">Error parsing markdown report.</p>`
        );
      } finally {
        this.cdr.detectChanges();
      }
    } else {
      this.reportHtml = '';
      this.cdr.detectChanges();
    }
  }

  runOnDemandAnalysis(): void {
    if (!this.stock) return;

    this.isAnalyzing = true;
    this.errorMessage = '';
    this.cdr.detectChanges();

    this.stockService.analyzeStock(this.stock.id, this.selectedModel).subscribe({
      next: (updatedReport) => {
        this.isAnalyzing = false;
        this.onAnalyze.emit(updatedReport);
        this.cdr.detectChanges();
      },
      error: (err) => {
        this.isAnalyzing = false;
        this.errorMessage = err.error?.detail || 'Failed to trigger Gemini on-demand analytics.';
        setTimeout(() => {
          this.errorMessage = '';
          this.cdr.detectChanges();
        }, 5000);
        this.cdr.detectChanges();
      }
    });
  }

  triggerDelete(): void {
    if (this.stock) {
      this.onDelete.emit({ id: this.stock.id });
    }
  }
}
