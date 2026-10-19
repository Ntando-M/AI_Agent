import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-base64-image',
  standalone: true,
  templateUrl: './base64-image.component.html',
  styleUrls: ['./base64-image.component.css'],
})
export class Base64ImageComponent {
  @Input() src = '';
  @Input() alt = '';
  @Input() loading: 'lazy' | 'eager' = 'lazy';
  @Input() maxWidth = '';
  @Input() maxHeight = '';
}
