import { Component, Input, Output, EventEmitter } from '@angular/core';

@Component({
  selector: 'app-chart-lightbox',
  standalone: true,
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
