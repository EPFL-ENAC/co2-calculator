// Equipment "power change request" mailto helpers (issue #266).
//
// When a user spots a wrong estimated power value on an equipment row, the second
// tab of the Comment dialog ("Demande de modification de puissance") shows a
// pre-filled, editable request text. On "Envoyer demande" we open a `mailto:` to
// an env-configured business admin, who updates the reference `Factor` manually.
//
// Both functions are pure (the body builder takes an injected translator) so they
// can be unit-tested for both locales without a live i18n runtime or a browser
// mail client.

export interface EquipmentPowerRequestData {
  equipmentName: string;
  equipmentClass: string;
  subClass?: string | null;
  currentActivePowerW?: number | null;
  currentStandbyPowerW?: number | null;
  unitName: string;
  year: string | number;
}

export type MailTranslate = (
  key: string,
  named?: Record<string, unknown>,
) => string;

const EM_DASH = '—';

function orDash(value: unknown): string {
  if (value === null || value === undefined) return EM_DASH;
  const str = String(value).trim();
  return str.length > 0 ? str : EM_DASH;
}

/**
 * Build the localized, pre-filled request text shown in the Tab-2 textarea. The
 * equipment context is filled in; the "new" active/standby power lines are left
 * blank for the user to complete (handled by the i18n template).
 */
export function buildPowerRequestBody(
  data: EquipmentPowerRequestData,
  t: MailTranslate,
): string {
  return t('equipment-power-feedback-request-template', {
    unitName: orDash(data.unitName),
    year: orDash(data.year),
    equipmentName: orDash(data.equipmentName),
    equipmentClass: orDash(data.equipmentClass),
    subClass: orDash(data.subClass),
    currentActivePowerW: orDash(data.currentActivePowerW),
    currentStandbyPowerW: orDash(data.currentStandbyPowerW),
  });
}

/**
 * Assemble a `mailto:` URL. The recipient is a plain email address (left raw,
 * matching the existing `mailto:${headOfUnitEmail}` usage); subject and body are
 * percent-encoded query values.
 */
export function buildMailtoUrl(
  recipient: string,
  subject: string,
  body: string,
): string {
  const query = `subject=${encodeURIComponent(
    subject,
  )}&body=${encodeURIComponent(body)}`;
  return `mailto:${recipient}?${query}`;
}
