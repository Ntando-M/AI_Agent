import { ApplicationConfig, provideBrowserGlobalErrorListeners } from '@angular/core';
import { provideHttpClient } from '@angular/common/http';

export const appConfig: ApplicationConfig = {
  providers: [
    provideBrowserGlobalErrorListeners(),

    // Provided here rather than per component so the API
    // service stays free of Angular wiring and can be
    // constructed directly in a test.
    provideHttpClient(),
  ]
};
