import { Component, Input, Output, EventEmitter } from '@angular/core';
import { AppIconComponent } from '../app-icon/app-icon.component';

@Component({
  selector: 'app-error-banner',
  standalone: true,
  imports: [AppIconComponent],
  templateUrl: './error-banner.component.html',
  styleUrls: ['./error-banner.component.css'],
})
export class ErrorBannerComponent {
  @Input() message = '';
  @Input() dismissible = true;
  @Output() dismiss = new EventEmitter<void>();
}
