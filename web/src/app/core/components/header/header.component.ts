import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterModule } from '@angular/router';
import { ThemeService } from '../../services/theme.service';
import { AppStateService } from '../../services/app-state.service';
import { AppIconComponent } from '../app-icon/app-icon.component';


@Component({
  selector: 'app-header',
  standalone: true,
  imports: [CommonModule, RouterModule, AppIconComponent],
  templateUrl: './header.component.html',
  styleUrls: ['./header.component.css'],
})
export class HeaderComponent {
  themeSvc = inject(ThemeService);
  appState = inject(AppStateService);

  toggleTheme(): void {
    this.themeSvc.toggle();
  }
}
