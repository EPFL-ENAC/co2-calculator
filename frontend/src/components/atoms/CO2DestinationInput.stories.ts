import type { Meta, StoryObj } from '@storybook/vue3';
import { ref } from 'vue';
import CO2DestinationInput from './CO2DestinationInput.vue';

/**
 * CO2DestinationInput is a component for selecting travel destinations with From and To fields.
 * It features a visual journey representation with markers and a swap button to exchange values.
 *
 * ## Features
 * - Two text inputs for "From" and "To" destinations with translated labels
 * - Visual markers (circles) connected by a vertical line on the left
 * - Swap button to exchange From and To values
 * - Error handling with visual feedback (red border and error message)
 * - Customizable placeholders
 */
const meta = {
  title: 'Atoms/CO2DestinationInput',
  component: CO2DestinationInput,
  tags: ['autodocs'],
  argTypes: {
    from: {
      control: 'text',
      description: 'The "From" destination value',
    },
    to: {
      control: 'text',
      description: 'The "To" destination value',
    },
    error: {
      control: 'boolean',
      description: 'Whether to show error state',
    },
    errorMessage: {
      control: 'text',
      description: 'Error message to display',
    },
    placeholders: {
      control: 'object',
      description: 'Placeholder text for From and To fields',
    },
  },
} satisfies Meta<typeof CO2DestinationInput>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default destination input with empty values.
 */
export const Default: Story = {
  render: () => {
    const from = ref('');
    const to = ref('');
    return {
      components: { CO2DestinationInput },
      setup() {
        return { from, to };
      },
      template: `
        <div style="padding: 24px; max-width: 600px;">
          <CO2DestinationInput
            :from="from"
            :to="to"
            @update:from="(val) => from = val"
            @update:to="(val) => to = val"
          />
          <div style="margin-top: 24px; padding: 16px; background: #f5f5f5; border-radius: 8px;">
            <p><strong>From:</strong> {{ from || '(empty)' }}</p>
            <p><strong>To:</strong> {{ to || '(empty)' }}</p>
          </div>
        </div>
      `,
    };
  },
};

/**
 * Destination input with pre-filled values.
 */
export const WithValues: Story = {
  render: () => {
    const from = ref('Paris');
    const to = ref('London');
    return {
      components: { CO2DestinationInput },
      setup() {
        return { from, to };
      },
      template: `
        <div style="padding: 24px; max-width: 600px;">
          <CO2DestinationInput
            :from="from"
            :to="to"
            @update:from="(val) => from = val"
            @update:to="(val) => to = val"
          />
          <div style="margin-top: 24px; padding: 16px; background: #f5f5f5; border-radius: 8px;">
            <p><strong>From:</strong> {{ from }}</p>
            <p><strong>To:</strong> {{ to }}</p>
          </div>
        </div>
      `,
    };
  },
};

/**
 * Destination input showing error state.
 */
export const WithError: Story = {
  render: () => {
    const from = ref('');
    const to = ref('');
    return {
      components: { CO2DestinationInput },
      setup() {
        return { from, to };
      },
      template: `
        <div style="padding: 24px; max-width: 600px;">
          <CO2DestinationInput
            :from="from"
            :to="to"
            :error="true"
            error-message="Both origin and destination are required"
            @update:from="(val) => from = val"
            @update:to="(val) => to = val"
          />
        </div>
      `,
    };
  },
};

/**
 * Destination input with placeholder text.
 */
export const WithPlaceholders: Story = {
  render: () => {
    const from = ref('');
    const to = ref('');
    return {
      components: { CO2DestinationInput },
      setup() {
        return { from, to };
      },
      template: `
        <div style="padding: 24px; max-width: 600px;">
          <CO2DestinationInput
            :from="from"
            :to="to"
            :placeholders="{ from: 'Enter origin city', to: 'Enter destination city' }"
            @update:from="(val) => from = val"
            @update:to="(val) => to = val"
          />
        </div>
      `,
    };
  },
};

/**
 * Destination input with all features: placeholders and values.
 */
export const FullFeatured: Story = {
  render: () => {
    const from = ref('Zurich');
    const to = ref('Geneva');
    return {
      components: { CO2DestinationInput },
      setup() {
        return { from, to };
      },
      template: `
        <div style="padding: 24px; max-width: 600px;">
          <CO2DestinationInput
            :from="from"
            :to="to"
            :placeholders="{ from: 'Enter departure city', to: 'Enter arrival city' }"
            @update:from="(val) => from = val"
            @update:to="(val) => to = val"
          />
          <div style="margin-top: 24px; padding: 16px; background: #f5f5f5; border-radius: 8px;">
            <p><strong>From:</strong> {{ from }}</p>
            <p><strong>To:</strong> {{ to }}</p>
          </div>
        </div>
      `,
    };
  },
};
