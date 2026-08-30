// A DOM for the XML readers when they run outside a browser.
//
// GPX and TCX are parsed with the platform DOMParser, which the browser supplies and Node does
// not. Registering a standards-compliant implementation as a global lets the Node suite cover
// the archive path end to end; the browser checks cover the same code against the real thing.
import { DOMParser } from '@xmldom/xmldom';

if (!globalThis.DOMParser) {
  globalThis.DOMParser = class extends DOMParser {
    constructor() {
      // xmldom reports malformed input through handlers rather than a parsererror element, so
      // errors are collected and rethrown to match what a browser does.
      const errors = [];
      super({
        onError: (level, msg) => { if (level === 'error' || level === 'fatalError') errors.push(msg); },
      });
      this._errors = errors;
    }

    parseFromString(text, type) {
      this._errors.length = 0;
      const doc = super.parseFromString(text, type);
      if (this._errors.length) {
        const err = doc.createElement('parsererror');
        err.textContent = this._errors.join('; ');
        doc.documentElement?.appendChild(err);
      }
      return doc;
    }
  };
}
