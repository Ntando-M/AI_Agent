import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-loading-spinner',
  standalone: true,
  templateUrl: './loading-spinner.component.html',
  styleUrls: ['./loading-spinner.component.css'],
})
export class LoadingSpinnerComponent {
  @Input() label = 'Loading...';
  @Input() size: 'sm' | 'md' | 'lg' = 'md';
}
