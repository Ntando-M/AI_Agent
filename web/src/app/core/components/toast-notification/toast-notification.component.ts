import { Component } from '@angular/core';
import { ToastService } from '../../services/toast.service';

import { AppIconComponent } from '../app-icon/app-icon.component';

@Component({
  selector: 'app-toast-notification',
  standalone: true,
  imports: [AppIconComponent],
  templateUrl: './toast-notification.component.html',
  styleUrls: ['./toast-notification.component.css'],
})
export class ToastNotificationComponent {
  constructor(public toastService: ToastService) {}

  toastIcon(type: string): string {
    switch (type) {
      case 'success': return 'check';
      case 'error': return 'close';
      case 'warning': return 'warning';
      default: return 'info';
    }
  }
}
