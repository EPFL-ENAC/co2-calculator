/**
 * Which blurs a dynamic form should validate (#2072).
 *
 * Quasar emits `QField`'s `blur` from a `setTimeout(…, 0)`
 * (`use-field.js`, `onControlFocusout`), and a `QBtn[type="submit"]` focuses
 * itself when the browser submits the form on Enter (`QBtn.js`, "focus button
 * if it came from ENTER on form"). `QForm` emits `submit` from a promise, i.e.
 * a microtask — which runs before that timer. So an Enter-key submit blurs the
 * focused field *after* the submit handler has already cleared the form, and
 * validating there flags a field the user did fill as "Required".
 *
 * A blur only says something about the user when the user was the one who put
 * focus there. Track that, and forget it whenever the form is cleared.
 */
export interface FieldInteractionTracker {
  /** Record that the user put focus in `fieldId`. */
  markInteracted(fieldId: string): void;
  /** Whether a blur on `fieldId` reflects a user interaction worth validating. */
  shouldValidateOnBlur(fieldId: string): boolean;
  /** Forget every interaction — call whenever the form is cleared. */
  clear(): void;
}

export function createFieldInteractionTracker(): FieldInteractionTracker {
  const interacted = new Set<string>();

  return {
    markInteracted(fieldId: string) {
      interacted.add(fieldId);
    },
    shouldValidateOnBlur(fieldId: string) {
      return interacted.has(fieldId);
    },
    clear() {
      interacted.clear();
    },
  };
}
