import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-skeleton-card',
  standalone: true,
  templateUrl: './skeleton-card.component.html',
  styleUrls: ['./skeleton-card.component.css'],
})
export class SkeletonCardComponent {
  @Input() height = '120px';
  @Input() width = '100%';
}
