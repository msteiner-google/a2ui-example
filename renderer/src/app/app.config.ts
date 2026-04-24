import { ApplicationConfig, provideBrowserGlobalErrorListeners, provideZoneChangeDetection } from '@angular/core';
import { provideRouter } from '@angular/router';
import { provideHttpClient } from '@angular/common/http';
import { marked } from 'marked';

import { routes } from './app.routes';
import { provideA2UI, DEFAULT_CATALOG, Types, registerStandardComponents, provideMarkdownRenderer, MessageProcessor } from '@a2ui/angular/v0_8';

// Ensure standard components are registered
registerStandardComponents(DEFAULT_CATALOG);

const EMPTY_RECORD = {};
const NO_OP_THEME: Types.Theme = {
  components: {
    AudioPlayer: EMPTY_RECORD,
    Button: EMPTY_RECORD,
    Card: EMPTY_RECORD,
    Column: EMPTY_RECORD,
    CheckBox: { container: EMPTY_RECORD, element: EMPTY_RECORD, label: EMPTY_RECORD },
    DateTimeInput: { container: EMPTY_RECORD, element: EMPTY_RECORD, label: EMPTY_RECORD },
    Divider: EMPTY_RECORD,
    Image: {
      all: EMPTY_RECORD,
      icon: EMPTY_RECORD,
      avatar: EMPTY_RECORD,
      smallFeature: EMPTY_RECORD,
      mediumFeature: EMPTY_RECORD,
      largeFeature: EMPTY_RECORD,
      header: EMPTY_RECORD,
    },
    Icon: EMPTY_RECORD,
    List: EMPTY_RECORD,
    Modal: { backdrop: EMPTY_RECORD, element: EMPTY_RECORD },
    MultipleChoice: { container: EMPTY_RECORD, element: EMPTY_RECORD, label: EMPTY_RECORD },
    Row: EMPTY_RECORD,
    Slider: { container: EMPTY_RECORD, element: EMPTY_RECORD, label: EMPTY_RECORD },
    Tabs: {
      container: EMPTY_RECORD,
      element: EMPTY_RECORD,
      controls: { all: EMPTY_RECORD, selected: EMPTY_RECORD },
    },
    Text: {
      all: EMPTY_RECORD,
      h1: EMPTY_RECORD,
      h2: EMPTY_RECORD,
      h3: EMPTY_RECORD,
      h4: EMPTY_RECORD,
      h5: EMPTY_RECORD,
      caption: EMPTY_RECORD,
      body: EMPTY_RECORD,
    },
    TextField: { container: EMPTY_RECORD, element: EMPTY_RECORD, label: EMPTY_RECORD },
    Video: EMPTY_RECORD,
  },
  elements: {
    a: EMPTY_RECORD,
    audio: EMPTY_RECORD,
    body: EMPTY_RECORD,
    button: EMPTY_RECORD,
    h1: EMPTY_RECORD,
    h2: EMPTY_RECORD,
    h3: EMPTY_RECORD,
    h4: EMPTY_RECORD,
    h5: EMPTY_RECORD,
    iframe: EMPTY_RECORD,
    input: EMPTY_RECORD,
    p: EMPTY_RECORD,
    pre: EMPTY_RECORD,
    textarea: EMPTY_RECORD,
    video: EMPTY_RECORD,
  },
  markdown: {
    p: [],
    h1: [],
    h2: [],
    h3: [],
    h4: [],
    h5: [],
    ul: [],
    ol: [],
    li: [],
    a: [],
    strong: [],
    em: [],
  },
};

export const appConfig: ApplicationConfig = {
  providers: [
    provideZoneChangeDetection({ eventCoalescing: true }),
    provideBrowserGlobalErrorListeners(),
    provideRouter(routes),
    provideHttpClient(),
    MessageProcessor, // Explicitly provide it
    provideA2UI({
    catalog: DEFAULT_CATALOG,
    theme: NO_OP_THEME,
    }),
    provideMarkdownRenderer(async (md: string) => {
    const html = await marked.parse(md);
    return html;
    }),
    ],
    };
