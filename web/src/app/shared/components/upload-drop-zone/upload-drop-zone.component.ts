import { Component, Input, Output, EventEmitter } from '@angular/core';

import { AppIconComponent } from '../../../core/components/app-icon/app-icon.component';

@Component({
  selector: 'app-upload-drop-zone',
  standalone: true,
  imports: [AppIconComponent],
  templateUrl: './upload-drop-zone.component.html',
  styleUrls: ['./upload-drop-zone.component.css'],
})
export class UploadDropZoneComponent {
  @Input() accept = '';
  @Input() maxSizeMb = 10;
  @Input() label = 'Drag files here or click to browse';
  @Input() hint = '';
  @Input() uploading = false;
  @Output() fileSelected = new EventEmitter<File>();

  isDragOver = false;

  onDragOver(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver = true;
  }

  onDragLeave(): void {
    this.isDragOver = false;
  }

  onDrop(event: DragEvent): void {
    event.preventDefault();
    this.isDragOver = false;
    const files = event.dataTransfer?.files;
    if (files && files.length > 0) {
      this.validateAndEmit(files[0]);
    }
  }

  onFileInput(event: Event): void {
    const input = event.target as HTMLInputElement;
    if (input.files && input.files.length > 0) {
      this.validateAndEmit(input.files[0]);
    }
  }

  private validateAndEmit(file: File): void {
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();
    const acceptedExts = this.accept.split(',').map(e => e.trim().toLowerCase());
    if (!acceptedExts.includes(ext)) {
      return;
    }
    if (file.size > this.maxSizeMb * 1024 * 1024) {
      return;
    }
    this.fileSelected.emit(file);
  }
}
