import {
  Component, Input, Output, EventEmitter, OnChanges, SimpleChanges,
  ChangeDetectorRef, HostListener
} from '@angular/core';
import { CommonModule } from '@angular/common';
import { StockService, MarketData, StockHolding } from '../../services/stock.service';
import { MarkdownToHtmlPipe } from '../../pipes/markdown-to-html.pipe';

interface AiVerdict { verdict: 'BUY' | 'SELL' | 'HOLD'; confidence: number; key_reasons: string[]; }

@Component({
  selector: 'app-stock-modal',
  standalone: true,
  imports: [CommonModule, MarkdownToHtmlPipe],
  templateUrl: './stock-modal.component.html',
  styleUrls: ['./stock-modal.component.css']
})
export class StockModalComponent implements OnChanges {
  Math = Math; // expose for template
  @Input() ticker: string | null = null;
  @Input() holding: StockHolding | null = null;   // populated if user holds this stock
  @Input() modelName: string = 'gemini-2.5-flash';
  @Output() closed = new EventEmitter<void>();

  // Data states
  marketData: MarketData | null = null;
  loadingMarket = false;
  marketError = '';

  reportMarkdown = '';
  aiVerdict: AiVerdict | null = null;
  loadingAI = false;
  aiError = '';

  // Chart settings
  readonly periods: ('1mo' | '3mo' | '6mo' | '1y')[] = ['1mo','3mo','6mo','1y'];
  period: '1mo' | '3mo' | '6mo' | '1y' = '3mo';
  chartMode: 'line' | 'candle' = 'line';

  // Hover state
  hoverIndex: number | null = null;

  // SVG dimensions
  readonly W = 700; readonly H = 220;
  readonly PL = 48; readonly PR = 12; readonly PT = 12; readonly PB = 24;
  readonly CW = this.W - this.PL - this.PR;
  readonly CH = this.H - this.PT - this.PB;

  readonly VH = 60; // volume chart height

  constructor(private stockService: StockService, private cdr: ChangeDetectorRef) {}

  @HostListener('document:keydown.escape') onEsc() { this.close(); }

  ngOnChanges(changes: SimpleChanges): void {
    if (changes['ticker'] && this.ticker) {
      this.load();
    }
  }

  close() { this.closed.emit(); }

  load(): void {
    if (!this.ticker) return;
    this.marketData = null; this.marketError = ''; this.loadingMarket = true;
    this.reportMarkdown = ''; this.aiVerdict = null; this.aiError = '';
    this.stockService.getMarketData(this.ticker, this.period).subscribe({
      next: (d) => { this.marketData = d; this.loadingMarket = false; this.cdr.detectChanges(); this.runAI(); },
      error: (e) => { this.marketError = e.error?.detail || 'Failed to load market data.'; this.loadingMarket = false; this.cdr.detectChanges(); }
    });
  }

  setPeriod(p: typeof this.period) { this.period = p; this.load(); }
  setChartMode(m: typeof this.chartMode) { this.chartMode = m; this.cdr.detectChanges(); }

  runAI(): void {
    if (!this.ticker) return;
    this.loadingAI = true; this.aiError = ''; this.aiVerdict = null;
    const holdingCtx = this.holding
      ? { quantity: this.holding.quantity, average_buy_price: this.holding.average_buy_price }
      : null;
    this.stockService.analyzeAnyTicker(this.ticker, holdingCtx, this.modelName).subscribe({
      next: (r) => {
        this.reportMarkdown = r.report;
        this.aiVerdict = this.parseVerdict(r.report);
        this.loadingAI = false; this.cdr.detectChanges();
      },
      error: (e) => { this.aiError = e.error?.detail || 'AI analysis failed.'; this.loadingAI = false; this.cdr.detectChanges(); }
    });
  }

  private parseVerdict(report: string): AiVerdict | null {
    try {
      const match = report.match(/```json\s*([\s\S]*?)\s*```/);
      if (match) return JSON.parse(match[1]);
    } catch {}
    return null;
  }

  get reportWithoutJson(): string {
    return this.reportMarkdown.replace(/```json[\s\S]*?```/g, '').trim();
  }

  // ── Chart helpers ──────────────────────────────────────────────────────────

  get chartDates(): string[] { return this.marketData?.dates ?? []; }
  get closes(): number[] { return this.marketData?.closes ?? []; }

  scaleX(i: number): number {
    const n = this.closes.length;
    return this.PL + (n < 2 ? 0 : (i / (n - 1)) * this.CW);
  }

  private priceRange(): { min: number; max: number } {
    const d = this.marketData!;
    const allVals = [
      ...d.closes, ...d.highs, ...d.lows,
      ...(d.bb.upper.filter(v => v !== null) as number[]),
      ...(d.bb.lower.filter(v => v !== null) as number[]),
    ];
    const min = Math.min(...allVals); const max = Math.max(...allVals);
    const pad = (max - min) * 0.05;
    return { min: min - pad, max: max + pad };
  }

  scaleY(price: number): number {
    const { min, max } = this.priceRange();
    return this.PT + this.CH - ((price - min) / (max - min || 1)) * this.CH;
  }

  get linePath(): string {
    return this.closes.map((p, i) => `${i === 0 ? 'M' : 'L'} ${this.scaleX(i).toFixed(1)} ${this.scaleY(p).toFixed(1)}`).join(' ');
  }

  get areaPath(): string {
    const bottom = this.PT + this.CH;
    const n = this.closes.length;
    return this.linePath + ` L ${this.scaleX(n - 1).toFixed(1)} ${bottom} L ${this.PL} ${bottom} Z`;
  }

  overlayPath(values: (number | null)[]): string {
    let path = ''; let first = true;
    values.forEach((v, i) => {
      if (v === null) { first = true; return; }
      path += `${first ? 'M' : 'L'} ${this.scaleX(i).toFixed(1)} ${this.scaleY(v).toFixed(1)} `;
      first = false;
    });
    return path.trim();
  }

  bbFillPath(): string {
    const upper = this.marketData!.bb.upper;
    const lower = this.marketData!.bb.lower;
    const validIdx = upper.map((v, i) => (v !== null && lower[i] !== null ? i : -1)).filter(i => i >= 0);
    if (!validIdx.length) return '';
    const top = validIdx.map(i => `${i === validIdx[0] ? 'M' : 'L'} ${this.scaleX(i).toFixed(1)} ${this.scaleY(upper[i]!).toFixed(1)}`).join(' ');
    const bot = [...validIdx].reverse().map(i => `L ${this.scaleX(i).toFixed(1)} ${this.scaleY(lower[i]!).toFixed(1)}`).join(' ');
    return `${top} ${bot} Z`;
  }

  // Candlestick data
  get candles(): { x: number; o: number; h: number; l: number; c: number; bullish: boolean }[] {
    const d = this.marketData!;
    return d.closes.map((c, i) => ({
      x: this.scaleX(i),
      o: this.scaleY(d.opens[i]),
      h: this.scaleY(d.highs[i]),
      l: this.scaleY(d.lows[i]),
      c: this.scaleY(c),
      bullish: c >= d.opens[i]
    }));
  }

  get candleWidth(): number {
    const n = this.closes.length;
    return Math.max(1, Math.min(8, (this.CW / n) * 0.6));
  }

  // Volume bars
  get maxVolume(): number { return Math.max(...(this.marketData?.volumes ?? [1])); }
  volumeBarHeight(v: number): number { return (v / this.maxVolume) * this.VH; }

  // RSI chart
  readonly RH = 70;
  get rsiValues(): (number | null)[] { return this.marketData?.rsi ?? []; }
  rsiY(v: number): number { return this.PT + this.RH - (v / 100) * this.RH; }

  get rsiPath(): string {
    let path = ''; let first = true;
    this.rsiValues.forEach((v, i) => {
      if (v === null) { first = true; return; }
      path += `${first ? 'M' : 'L'} ${this.scaleX(i).toFixed(1)} ${this.rsiY(v).toFixed(1)} `;
      first = false;
    });
    return path.trim();
  }

  // MACD chart
  readonly MH = 60;
  get macdData() { return this.marketData?.macd; }
  get macdRange(): { min: number; max: number } {
    const vals = [
      ...(this.macdData?.histogram.filter(v => v !== null) as number[] ?? []),
      ...(this.macdData?.macd.filter(v => v !== null) as number[] ?? []),
    ];
    if (!vals.length) return { min: -1, max: 1 };
    return { min: Math.min(...vals) * 1.1, max: Math.max(...vals) * 1.1 };
  }
  macdY(v: number): number {
    const { min, max } = this.macdRange;
    return this.PT + this.MH / 2 - (v / (max - min || 1)) * this.MH;
  }
  macdLinePath(values: (number | null)[]): string {
    let path = ''; let first = true;
    values.forEach((v, i) => {
      if (v === null) { first = true; return; }
      path += `${first ? 'M' : 'L'} ${this.scaleX(i).toFixed(1)} ${this.macdY(v).toFixed(1)} `;
      first = false;
    });
    return path.trim();
  }
  get macdZeroY(): number { return this.macdY(0); }

  // Price axis ticks
  get priceAxis(): { y: number; label: string }[] {
    if (!this.marketData) return [];
    const { min, max } = this.priceRange();
    const ticks = 5;
    return Array.from({ length: ticks }, (_, i) => {
      const v = min + ((max - min) * i) / (ticks - 1);
      return { y: this.scaleY(v), label: v >= 1000 ? `₹${(v / 1000).toFixed(1)}k` : `₹${v.toFixed(0)}` };
    }).reverse();
  }

  // Hover crosshair
  onChartMouseMove(e: MouseEvent, svgEl: SVGElement): void {
    const rect = svgEl.getBoundingClientRect();
    const x = (e.clientX - rect.left) / rect.width * this.W;
    const n = this.closes.length;
    if (n < 2) return;
    const idx = Math.round(((x - this.PL) / this.CW) * (n - 1));
    this.hoverIndex = Math.max(0, Math.min(n - 1, idx));
    this.cdr.detectChanges();
  }
  onChartMouseLeave(): void { this.hoverIndex = null; this.cdr.detectChanges(); }

  get hoverX(): number { return this.hoverIndex !== null ? this.scaleX(this.hoverIndex) : 0; }
  get hoverPrice(): number { return this.hoverIndex !== null ? this.closes[this.hoverIndex] : 0; }
  get hoverDate(): string { return this.hoverIndex !== null ? this.chartDates[this.hoverIndex] : ''; }
  get hoverVolume(): number { return this.hoverIndex !== null ? (this.marketData?.volumes[this.hoverIndex] ?? 0) : 0; }

  // Verdict helpers
  get verdictColor(): string {
    if (!this.aiVerdict) return '#8E95A5';
    return this.aiVerdict.verdict === 'BUY' ? '#00E699' : this.aiVerdict.verdict === 'SELL' ? '#FF4D4D' : '#F59E0B';
  }
  get verdictBg(): string {
    if (!this.aiVerdict) return 'rgba(142,149,165,0.1)';
    return this.aiVerdict.verdict === 'BUY' ? 'rgba(0,230,153,0.1)' : this.aiVerdict.verdict === 'SELL' ? 'rgba(255,77,77,0.1)' : 'rgba(245,158,11,0.1)';
  }

  // Signal display helpers
  signalColor(val: string): string {
    const pos = new Set(['GOLDEN_CROSS','OVERSOLD','NEAR_LOWER','ABOVE_AVG','BULLISH']);
    const neg = new Set(['DEATH_CROSS','OVERBOUGHT','NEAR_UPPER','BEARISH']);
    if (pos.has(val)) return '#00E699';
    if (neg.has(val)) return '#FF4D4D';
    return '#8E95A5';
  }

  // 52W position bar
  get week52Pct(): number {
    if (!this.marketData) return 0;
    const { week52_low: lo, week52_high: hi, current_price: p } = this.marketData;
    return Math.min(100, Math.max(0, ((p - lo) / (hi - lo || 1)) * 100));
  }

  // Holding P&L
  get holdingPnL(): number {
    if (!this.holding || !this.marketData) return 0;
    return (this.marketData.current_price - this.holding.average_buy_price) * this.holding.quantity;
  }
  get holdingPnLPct(): number {
    if (!this.holding) return 0;
    return ((this.marketData!.current_price - this.holding.average_buy_price) / this.holding.average_buy_price) * 100;
  }
  get dailyChange(): number {
    if (!this.marketData || this.marketData.closes.length < 2) return 0;
    const c = this.marketData.closes;
    return ((c[c.length - 1] - c[c.length - 2]) / c[c.length - 2]) * 100;
  }
}
