import { Injectable } from '@angular/core';
import { HttpClient, HttpParams } from '@angular/common/http';
import { Observable } from 'rxjs';

export interface StockMetricsSnapshot {
  id: string;
  stock_id: string;
  current_price: number;
  trailing_pe: number | null;
  market_cap: number | null;
  fifty_two_week_high: number;
  fifty_two_week_low: number;
  price_history_7d: number[];
  volume: number | null;
  fetched_at: string;
}

export interface GeminiAnalysisReport {
  id: string;
  stock_id: string;
  analysis_report: string;
  trigger_type: string;
  created_at: string;
}

export interface StockWatchlistResponse {
  id: string;
  ticker: string;
  company_name: string | null;
  added_at: string;
  latest_metrics: StockMetricsSnapshot | null;
  latest_report: GeminiAnalysisReport | null;
}

export interface MarketDirectoryEntry {
  ticker: string;
  company_name: string;
  current_price: number;
  change_percentage: number;
  volume: number;
}

export interface StockHolding {
  id: string;
  ticker: string;
  company_name: string | null;
  quantity: number;
  average_buy_price: number;
  updated_at: string;
}

export interface MarketDataSignals {
  rsi_value: number;
  rsi_signal: 'OVERBOUGHT' | 'OVERSOLD' | 'NEUTRAL';
  ma_cross: 'GOLDEN_CROSS' | 'DEATH_CROSS' | 'NEUTRAL';
  bb_position: 'NEAR_UPPER' | 'NEAR_LOWER' | 'MID';
  volume_trend: 'ABOVE_AVG' | 'BELOW_AVG';
  macd_signal: 'BULLISH' | 'BEARISH';
  price_vs_52w_high_pct: number;
  price_vs_52w_low_pct: number;
}

export interface MarketData {
  ticker: string;
  company_name: string;
  current_price: number;
  market_cap: number | null;
  trailing_pe: number | null;
  forward_pe: number | null;
  dividend_yield: number | null;
  beta: number | null;
  sector: string;
  industry: string;
  week52_high: number;
  week52_low: number;
  avg_volume: number;
  period: string;
  dates: string[];
  opens: number[];
  highs: number[];
  lows: number[];
  closes: number[];
  volumes: number[];
  ma20: (number | null)[];
  ma50: (number | null)[];
  ma200: (number | null)[];
  rsi: (number | null)[];
  bb: { mid: (number | null)[]; upper: (number | null)[]; lower: (number | null)[] };
  macd: { macd: (number | null)[]; signal: (number | null)[]; histogram: (number | null)[] };
  signals: MarketDataSignals;
}

@Injectable({
  providedIn: 'root'
})
export class StockService {
  private apiUrl = '/api/stocks';
  private holdingsUrl = '/api/holdings';
  private directoryUrl = '/api/directory';

  constructor(private http: HttpClient) {}

  getStocks(): Observable<StockWatchlistResponse[]> {
    return this.http.get<StockWatchlistResponse[]>(this.apiUrl);
  }

  addStock(ticker: string, modelName?: string): Observable<StockWatchlistResponse> {
    let params = new HttpParams();
    if (modelName) {
      params = params.set('model_name', modelName);
    }
    return this.http.post<StockWatchlistResponse>(this.apiUrl, { ticker }, { params });
  }

  deleteStock(id: string): Observable<void> {
    return this.http.delete<void>(`${this.apiUrl}/${id}`);
  }

  analyzeStock(id: string, modelName?: string): Observable<GeminiAnalysisReport> {
    let params = new HttpParams();
    if (modelName) {
      params = params.set('model_name', modelName);
    }
    return this.http.post<GeminiAnalysisReport>(`${this.apiUrl}/${id}/analyze`, {}, { params });
  }

  // Market Directory
  getDirectory(query: string = ''): Observable<MarketDirectoryEntry[]> {
    let params = new HttpParams();
    if (query) params = params.set('q', query);
    return this.http.get<MarketDirectoryEntry[]>(this.directoryUrl, { params });
  }

  // Portfolio Holdings
  getHoldings(): Observable<StockHolding[]> {
    return this.http.get<StockHolding[]>(this.holdingsUrl);
  }

  addHolding(ticker: string, quantity: number, average_buy_price: number): Observable<StockHolding> {
    return this.http.post<StockHolding>(this.holdingsUrl, { ticker, quantity, average_buy_price });
  }

  deleteHolding(id: string): Observable<void> {
    return this.http.delete<void>(`${this.holdingsUrl}/${id}`);
  }

  // Rich market data + any-ticker AI analysis
  getMarketData(ticker: string, period: string = '3mo'): Observable<MarketData> {
    return this.http.get<MarketData>(`/api/market-data/${ticker}`, { params: new HttpParams().set('period', period) });
  }

  analyzeAnyTicker(ticker: string, holdingContext: { quantity: number; average_buy_price: number } | null, modelName: string = 'gemini-2.5-flash'): Observable<{ ticker: string; report: string }> {
    return this.http.post<{ ticker: string; report: string }>(
      `/api/analyze/${ticker}`,
      { holding_context: holdingContext },
      { params: new HttpParams().set('model_name', modelName) }
    );
  }
}
