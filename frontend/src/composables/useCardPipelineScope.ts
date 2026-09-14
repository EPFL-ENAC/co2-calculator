import { computed, inject, type ComputedRef } from 'vue';
import { resolvePipelinePhaseLabelKey } from '@/composables/pipelinePhaseLabel';
import { TargetType } from '@/constant/ingestion';
import type { ImportRow } from '@/stores/backofficeDataManagement';
import type { PipelineJob, PipelineProgress } from '@/stores/pipelineStream';

interface CardScopeProps {
  pipelineProgress?: PipelineProgress | null;
  targetType?: TargetType;
  row?: ImportRow;
}

/** Which live-pipeline phase (if any) an upload card should surface. */
export function useCardPipelineScope(props: CardScopeProps) {
  // Issue #1219 — live recalc-pipeline phase for this card.
  //
  // Pipeline progress is module-scoped (provided by ModuleConfig as the
  // single SSE subscriber) AND kind-scoped: a factor_ingest pipeline
  // shouldn't surface its phase on the data card and vice versa.
  // ``pipelineAppliesToCard`` gates rendering on ``progress.kind``
  // matching this card's ``targetType`` — empty kind (orphan / unknown
  // root) falls back to "don't render" rather than risk showing on the
  // wrong card.
  //
  // Phase-label vocabulary (3-step ingest map vs. the recalc-kind's
  // single collapsed label) lives in ``resolvePipelinePhaseLabelKey`` —
  // see that file for why it's a shared pure helper.
  const TARGET_TO_KINDS: Record<number, ReadonlyArray<string>> = {
    // TargetType.DATA_ENTRIES = 0 — every pipeline whose work targets
    // the data-entries domain belongs on the data card:
    //   * csv_ingest / api_ingest — user uploads or admin sync.
    //   * emission_recalc / module_emission_recalc — pipelines minted by
    //     POST /sync/recalculate-emissions/{module}[/{det}] when the
    //     operator clicks the "Recalculate" button on the data card.
    //     Their kind is set at the parent's ensure_pipeline_exists call
    //     in data_sync.py:1610 + :1710.  Without these the recalc
    //     pipeline runs but the data card stays blank — confusing
    //     because the button that triggered it IS on the data card.
    [TargetType.DATA_ENTRIES]: [
      'csv_ingest',
      'api_ingest',
      'emission_recalc',
      'module_emission_recalc',
    ],
    // TargetType.FACTORS = 1 — the parent is always factor_ingest.
    [TargetType.FACTORS]: ['factor_ingest'],
    // TargetType.REFERENCE_DATA = 3 — reference uploads (building rooms,
    // travel reference) chain through reference_ingest.
    [TargetType.REFERENCE_DATA]: ['reference_ingest'],
  };

  // Dets actually present in the live pipeline (provided by ModuleConfig
  // as ``livePipelineJobsById``).  A single-submodule upload recalcs only
  // its own det, so its sibling submodule cards must NOT show the
  // emissions/aggregation phase.  Module-wide uploads fan out a recalc
  // per det, so every det lands here and all cards light up — both
  // correct.  Empty when no pipeline is active or this card renders
  // outside ModuleConfig (fixtures), which disables det-scoping below.
  const livePipelineJobsById = inject<
    ComputedRef<ReadonlyMap<number, PipelineJob>>
  >(
    'livePipelineJobsById',
    computed(() => new Map()),
  );

  const pipelineDataEntryTypeIds = computed<Set<number>>(() => {
    const ids = new Set<number>();
    for (const job of livePipelineJobsById.value.values()) {
      if (job.data_entry_type_id != null) ids.add(job.data_entry_type_id);
    }
    return ids;
  });

  const pipelineAppliesToCard = computed<boolean>(() => {
    const p = props.pipelineProgress;
    if (!p) return false;
    if (props.targetType === undefined) return false;
    const allowedKinds = TARGET_TO_KINDS[props.targetType];
    if (!allowedKinds || !p.kind) return false;
    if (!allowedKinds.includes(p.kind)) return false;
    // Det-scoping: when this card maps to a specific submodule det and
    // the pipeline declares which dets it touches, only show the phase
    // if this card's det is among them.  A module-level card (no det)
    // or an empty det set (module-wide ingest before recalc fan-out, or
    // older payloads without the field) falls through to "show" —
    // preserving prior behavior.
    const det = props.row?.dataEntryTypeId;
    const detSet = pipelineDataEntryTypeIds.value;
    if (det != null && detSet.size > 0) {
      return detSet.has(det);
    }
    return true;
  });

  const pipelinePhaseLabelKey = computed<string | null>(() => {
    if (!pipelineAppliesToCard.value) return null;
    const p = props.pipelineProgress;
    if (!p || p.done || p.has_error) return null;
    return resolvePipelinePhaseLabelKey(p.phase_label, p.kind);
  });

  // Pipeline-in-progress flag for the "validated" ✓ indicator below.
  // Same card-scoping rule: a factor upload's running pipeline shouldn't
  // turn the data card's ✓ amber.  Gated on ``pipelineAppliesToCard``.
  const pipelineStillRunning = computed<boolean>(() => {
    if (!pipelineAppliesToCard.value) return false;
    const p = props.pipelineProgress;
    return !!(p && !p.done);
  });

  // A new CSV upload or API sync replaces the data shown on this card. Keep the
  // live phase as the single source of truth until that ingest finishes, rather
  // than showing stale API results beside it. Downstream recalculation phases do
  // not hide the finished ingestion summary.
  const dataIngestionRunning = computed<boolean>(() => {
    if (!pipelineAppliesToCard.value) return false;
    const p = props.pipelineProgress;
    return !!(
      p &&
      !p.done &&
      (p.kind === 'csv_ingest' || p.kind === 'api_ingest')
    );
  });

  return { pipelinePhaseLabelKey, pipelineStillRunning, dataIngestionRunning };
}
