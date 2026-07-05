import { test, expect } from '@playwright/test';

test.describe('AI Stock Intelligence Platform E2E Integration Flow', () => {
  
  test('should validate, register, analyze, and delete Vedanta (VEDL.NS) using live data', async ({ page }) => {
    // Enable browser log mirroring
    page.on('console', msg => console.log('BROWSER CONSOLE:', msg.text()));
    page.on('pageerror', err => console.error('BROWSER PAGEERROR:', err.message));

    // 1. Clear out any preexisting stocks via API to maintain test isolation
    const watchlistRes = await page.request.get('/api/stocks');
    if (watchlistRes.ok()) {
      const stocks = await watchlistRes.json();
      for (const stock of stocks) {
        await page.request.delete(`/api/stocks/${stock.id}`);
      }
    }

    // 2. Load the platform landing dashboard (redirects to /watchlist)
    await page.goto('/');
    
    // Wait for the watchlist container to render either the empty state or stock cards
    await page.locator('h3:has-text("Watchlist Empty"), section .bg-slatecard').first().waitFor({ state: 'visible', timeout: 15000 });

    // Verify core styling/branding elements are visible
    await expect(page.locator('h1')).toContainText('ANTIGRAVITY STOCK INTELLIGENCE');

    // Verify nav links are rendered
    await expect(page.locator('a[href="/watchlist"]')).toBeVisible();
    await expect(page.locator('a[href="/holdings"]')).toBeVisible();
    await expect(page.locator('a[href="/directory"]')).toBeVisible();
    
    // Verify workspace reports Empty State
    await expect(page.locator('h3:has-text("Watchlist Empty")')).toBeVisible();

    // 3. Register Vedanta Limited (VEDL.NS) — uses new ticker input id
    await page.locator('#ticker-input').fill('VEDL.NS');
    await page.locator('button:has-text("VALIDATE & REGISTER")').click();
    
    // 4. Verify card is appended to watchlist (allow up to 25s for live network calls)
    const stockCard = page.locator('section').first().locator('.bg-slatecard', { hasText: 'VEDL.NS' });
    try {
      await expect(stockCard).toBeVisible({ timeout: 25000 });
    } catch (err) {
      console.log("DEBUG PAGE HTML ON FAILURE:", await page.content());
      throw err;
    }
    
    // 5. Select the Vedanta card
    await stockCard.click();
    
    // 6. Verify details panel compiles numerical and company data
    const detailPanel = page.locator('app-stock-detail');
    await expect(detailPanel.locator('h2').first()).toContainText('VEDL.NS — Vedanta Limited');
    
    // Verify pricing metrics are loaded
    const currentPrice = detailPanel.locator('.text-xl').first();
    await expect(currentPrice).not.toContainText('$0.00');
    await expect(detailPanel).toContainText('Daily Volume');
    
    // 7. Verify Gemini report is rendered
    const markdownContainer = detailPanel.locator('.gemini-markdown');
    await expect(markdownContainer).toBeVisible();
    
    const reportText = await markdownContainer.innerText();
    expect(reportText.length).toBeGreaterThan(50);
    
    // 8. Trigger manual on-demand analysis
    const analyzeButton = detailPanel.locator('button:has-text("RUN ON-DEMAND AI ANALYSIS")');
    await analyzeButton.click();
    
    // Wait for manual analysis to complete (allow up to 25s for Gemini API response)
    await expect(analyzeButton).toBeEnabled({ timeout: 25000 });
    
    // 9. Delete the stock
    await detailPanel.locator('button:has-text("DELETE STOCK")').click();
    
    // Watchlist should be returned to clean empty state
    await expect(page.locator('h3:has-text("Watchlist Empty")')).toBeVisible();
  });
});
