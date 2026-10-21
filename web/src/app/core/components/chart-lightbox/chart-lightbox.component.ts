import { Component, Input, Output, EventEmitter } from '@angular/core';
import { AppIconComponent } from '../app-icon/app-icon.component';

@Component({
  selector: 'app-chart-lightbox',
  standalone: true,
  imports: [AppIconComponent],
  templateUrl: './chart-lightbox.component.html',
  styleUrls: ['./chart-lightbox.component.css'],
})
export class ChartLightboxComponent {
  @Input() src = '';
  @Input() alt = '';
  @Output() close = new EventEmitter<void>();

  onBackdropClick(): void {
    this.close.emit();
  }
}
