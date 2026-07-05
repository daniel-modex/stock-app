import { Routes } from '@angular/router';
import { DashboardComponent } from './components/dashboard/dashboard.component';
import { HoldingsComponent } from './components/holdings/holdings.component';
import { DirectoryComponent } from './components/directory/directory.component';

export const routes: Routes = [
  { path: '', redirectTo: 'watchlist', pathMatch: 'full' },
  { path: 'watchlist', component: DashboardComponent },
  { path: 'holdings', component: HoldingsComponent },
  { path: 'directory', component: DirectoryComponent },
  { path: '**', redirectTo: 'watchlist' }
];
