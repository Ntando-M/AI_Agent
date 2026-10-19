import { Component, Input } from '@angular/core';

@Component({
  selector: 'app-data-table',
  standalone: true,
  templateUrl: './data-table.component.html',
  styleUrls: ['./data-table.component.css'],
})
export class DataTableComponent {
  @Input() columns: string[] = [];
  @Input() rows: Record<string, any>[] = [];
  @Input() maxRows = 10;
}
