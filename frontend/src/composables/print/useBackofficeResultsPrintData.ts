import { computed } from 'vue';
import { useBackofficePrintBase } from './useBackofficePrintBase';

export function useBackofficeResultsPrintData() {
  const base = useBackofficePrintBase();
  const { filters, reportingEmissionBreakdown } = base;

  const years = computed<string[]>(() => filters.value.years ?? []);

  const totalTonnes = computed(
    () => reportingEmissionBreakdown.value?.total_tonnes_co2eq ?? null,
  );
  const totalFte = computed(
    () => reportingEmissionBreakdown.value?.total_fte ?? null,
  );
  const tonnesPerFte = computed(() => {
    const t = totalTonnes.value;
    const f = totalFte.value;
    if (t == null || !f || f <= 0) return null;
    return t / f;
  });

  const perPersonBreakdown = computed(
    () => reportingEmissionBreakdown.value?.per_person_breakdown ?? null,
  );
  const validatedCategories = computed(
    () => reportingEmissionBreakdown.value?.validated_categories ?? null,
  );
  const headcountValidated = computed(
    () => reportingEmissionBreakdown.value?.headcount_validated ?? false,
  );

  return {
    ...base,
    years,
    totalTonnes,
    totalFte,
    tonnesPerFte,
    perPersonBreakdown,
    validatedCategories,
    headcountValidated,
  };
}
