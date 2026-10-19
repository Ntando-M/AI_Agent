import { Component, inject } from '@angular/core';
import { CommonModule } from '@angular/common';
import { RouterLink, RouterLinkActive } from '@angular/router';
import { AppStateService } from '../../services/app-state.service';
import { AppIconComponent } from '../app-icon/app-icon.component';

@Component({
  selector: 'app-sidebar',
  standalone: true,
  imports: [CommonModule, RouterLink, RouterLinkActive, AppIconComponent],
  templateUrl: './sidebar.component.html',
  styleUrls: ['./sidebar.component.css'],
})
export class SidebarComponent {
  appState = inject(AppStateService);

  toggleCollapse(): void {
    this.appState.sidebarCollapsed.update(c => !c);
  }
}
