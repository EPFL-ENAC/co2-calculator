<template>
  <q-card flat bordered class="q-pa-md q-mb-xl">
    <div class="text-subtitle1">
      {{ $t('data_management_connectors_title') }}
    </div>
    <div class="text-body2 text-secondary q-mb-md">
      {{ $t('data_management_connectors_hint') }}
    </div>
    <q-list separator>
      <q-item v-for="spec in connectors" :key="spec.connector">
        <q-item-section>
          <q-item-label>{{ spec.label }}</q-item-label>
        </q-item-section>
        <q-item-section side>
          <q-chip
            dense
            square
            :color="connectionStatus[spec.connector] ? 'positive' : 'grey-4'"
            :text-color="connectionStatus[spec.connector] ? 'white' : 'grey-9'"
          >
            {{
              connectionStatus[spec.connector]
                ? $t('data_management_connector_configured')
                : $t('data_management_connector_not_configured')
            }}
          </q-chip>
        </q-item-section>
        <q-item-section side>
          <q-btn
            dense
            outline
            color="grey-8"
            class="text-weight-medium text-capitalize"
            :label="$t('data_management_configure_connection')"
            @click="openDialog(spec)"
          />
        </q-item-section>
      </q-item>
    </q-list>
  </q-card>

  <q-dialog v-model="showDialog">
    <q-card style="width: 480px; max-width: 90vw">
      <q-card-section class="row items-center justify-between">
        <div class="text-h6">
          {{
            $t('data_management_configure_connector_title', {
              connector: activeSpec?.label,
            })
          }}
        </div>
        <q-btn v-close-popup flat round dense icon="o_close" color="grey-6" />
      </q-card-section>
      <q-separator />
      <q-card-section class="q-gutter-sm">
        <q-input
          v-if="activeSpec?.form_fields.includes('server_url')"
          v-model="serverUrl"
          dense
          outlined
          :label="$t('data_management_api_server_url')"
        />
        <q-input
          v-if="activeSpec?.form_fields.includes('site_content_url')"
          v-model="siteContentUrl"
          dense
          outlined
          :label="$t('data_management_api_site_content_url')"
        />
        <q-input
          v-if="activeSpec?.form_fields.includes('username')"
          v-model="username"
          dense
          outlined
          :label="$t('data_management_api_username')"
        />
        <q-input
          v-if="activeSpec?.form_fields.includes('client_id')"
          v-model="clientId"
          dense
          outlined
          :label="$t('data_management_api_client_id')"
        />
        <q-input
          v-if="activeSpec?.form_fields.includes('secret_id')"
          v-model="secretId"
          dense
          outlined
          :label="$t('data_management_api_secret_id')"
        />
        <q-input
          v-if="activeSpec?.form_fields.includes('secret_value')"
          v-model="secretValue"
          dense
          outlined
          type="password"
          auto-complete="current-password"
          :label="$t('data_management_api_secret_value')"
          :hint="
            hasExistingSecret
              ? $t('data_management_api_secret_kept')
              : undefined
          "
        />
      </q-card-section>
      <q-card-actions align="right">
        <q-btn
          outline
          dense
          color="grey-8"
          class="text-weight-medium text-capitalize"
          :label="$t('data_management_api_test_connection')"
          :loading="isTesting"
          :disable="!canTest || isTesting"
          @click="testConnectionNow"
        />
        <q-btn
          color="accent"
          unelevated
          class="text-weight-medium"
          :label="$t('common_save')"
          :loading="isSaving"
          :disable="!canTest || isSaving"
          @click="saveConnection"
        />
      </q-card-actions>
    </q-card>
  </q-dialog>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue';
import { Notify } from 'quasar';
import { useI18n } from 'vue-i18n';
import {
  useConnectorsStore,
  type ConnectorSpecRead,
} from 'src/stores/connectors';

const connectorsStore = useConnectorsStore();
const { t } = useI18n();

const connectors = ref<ConnectorSpecRead[]>([]);
const connectionStatus = ref<Record<string, boolean>>({});

const showDialog = ref(false);
const activeSpec = ref<ConnectorSpecRead | null>(null);
const serverUrl = ref('');
const siteContentUrl = ref('');
const username = ref('');
const clientId = ref('');
const secretId = ref('');
const secretValue = ref('');
const hasExistingSecret = ref(false);
const isSaving = ref(false);
const isTesting = ref(false);

const canTest = computed(
  () =>
    !!serverUrl.value &&
    !!username.value &&
    !!clientId.value &&
    !!secretId.value &&
    (hasExistingSecret.value || !!secretValue.value),
);

onMounted(load);

async function load() {
  connectors.value = await connectorsStore.listConnectors();
  for (const spec of connectors.value) {
    const conn = await connectorsStore.getConnection(spec.connector);
    connectionStatus.value[spec.connector] = !!conn;
  }
}

async function openDialog(spec: ConnectorSpecRead) {
  activeSpec.value = spec;
  const conn = await connectorsStore.getConnection(spec.connector);
  hasExistingSecret.value = !!conn?.has_secret;
  serverUrl.value = conn?.server_url ?? '';
  siteContentUrl.value = conn?.site_content_url ?? '';
  username.value = conn?.username ?? '';
  clientId.value = conn?.client_id ?? '';
  secretId.value = conn?.secret_id ?? '';
  secretValue.value = '';
  showDialog.value = true;
}

function buildPayload() {
  return {
    label: activeSpec.value?.label ?? '',
    server_url: serverUrl.value,
    site_content_url: siteContentUrl.value || undefined,
    username: username.value,
    client_id: clientId.value,
    secret_id: secretId.value,
    secret_value: secretValue.value || undefined,
  };
}

async function saveConnection() {
  if (!activeSpec.value) return;
  isSaving.value = true;
  try {
    await connectorsStore.saveConnection(
      activeSpec.value.connector,
      buildPayload(),
    );
    connectionStatus.value[activeSpec.value.connector] = true;
    Notify.create({
      type: 'positive',
      message: t('data_management_connection_saved'),
      position: 'top',
    });
    showDialog.value = false;
  } catch (err: unknown) {
    Notify.create({
      type: 'negative',
      message: t('data_management_connection_failed'),
      caption: err instanceof Error ? err.message : undefined,
      position: 'top',
    });
  } finally {
    isSaving.value = false;
  }
}

async function testConnectionNow() {
  if (!activeSpec.value) return;
  isTesting.value = true;
  try {
    // Save first — the backend tests the stored connection, not
    // in-flight form values (PRD: "test connection" is a sub-step of
    // entering the connection).
    await connectorsStore.saveConnection(
      activeSpec.value.connector,
      buildPayload(),
    );
    connectionStatus.value[activeSpec.value.connector] = true;
    const result = await connectorsStore.testConnection(
      activeSpec.value.connector,
    );
    Notify.create({
      type: result.ok ? 'positive' : 'negative',
      message: result.ok
        ? t('data_management_connection_success')
        : t('data_management_connection_failed'),
      caption: result.detail,
      position: 'top',
    });
  } catch (err: unknown) {
    Notify.create({
      type: 'negative',
      message: t('data_management_connection_failed'),
      caption: err instanceof Error ? err.message : undefined,
      position: 'top',
    });
  } finally {
    isTesting.value = false;
  }
}
</script>
