import { Component, Input, Output, EventEmitter } from '@angular/core';
import { AppIconComponent } from '../app-icon/app-icon.component';

@Component({
  selector: 'app-empty-state',
  standalone: true,
  imports: [AppIconComponent],
  templateUrl: './empty-state.component.html',
  styleUrls: ['./empty-state.component.css'],
})
export class EmptyStateComponent {
  @Input() icon = 'chat';
  @Input() title = 'Nothing here yet';
  @Input() message = '';
  @Input() ctaLabel = '';
  @Output() cta = new EventEmitter<void>();
}
