import { nOrDash } from 'src/utils/number';
import { i18n } from 'src/boot/i18n';

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $nOrDash: typeof nOrDash;
    $t: typeof i18n.global.t;
  }
}

export {};
