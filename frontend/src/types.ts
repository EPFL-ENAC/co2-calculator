import {
  nOrDash,
  formatTonnesCO2,
  formatKgCO2,
  formatFTE,
} from 'src/utils/number';
import { i18n } from 'src/boot/i18n';

declare module '@vue/runtime-core' {
  interface ComponentCustomProperties {
    $nOrDash: typeof nOrDash;
    $formatTonnesCO2: typeof formatTonnesCO2;
    $formatKgCO2: typeof formatKgCO2;
    $formatFTE: typeof formatFTE;
    $t: typeof i18n.global.t;
    $n: typeof i18n.global.n;
  }
}

export {};
