import type { Meta, StoryObj } from '@storybook/vue3';
import { QBtn } from 'quasar';

/**
 * Button component documentation showcasing all q-btn styling variations used in the CO2 Calculator project.
 *
 * ## Overview
 * This Storybook showcases all the different styling patterns and props used with Quasar's q-btn component
 * throughout the application. Each story demonstrates a specific use case with code examples.
 *
 * ## Common Props Used
 * - `color`: Button color (accent, primary, grey-4, info, etc.)
 * - `size`: Button size (xs, sm, md, lg)
 * - `unelevated`: Removes elevation/shadow (most buttons use this)
 * - `outline`: Outlined button style (used for secondary buttons)
 * - `dense`: Reduces padding for compact buttons
 * - `no-caps`: Prevents text transformation to uppercase
 * - `rounded`: Rounded button style
 * - `square`: Square button style
 * - `round`: Circular button (for icon-only)
 * - `icon`: Icon name (Material Icons, use "o_" prefix for outlined icons)
 * - `label`: Button text label
 * - `fullwidth`: Full width button
 * - `disabled`: Disabled state
 */
const meta = {
  title: 'Atoms/Button',
  component: QBtn,
  tags: ['autodocs'],
  argTypes: {
    color: {
      control: 'select',
      options: [
        'accent',
        'primary',
        'grey-4',
        'info',
        'negative',
        'positive',
        'warning',
      ],
    },
    size: {
      control: 'select',
      options: ['xs', 'sm', 'md', 'lg'],
    },
    label: {
      control: 'text',
      description: 'Button text label',
    },
    icon: {
      control: 'text',
      description:
        'Icon name (Material Icons, use "o_" prefix for outlined icons)',
    },
    unelevated: {
      control: 'boolean',
      description: 'Removes elevation/shadow',
    },
    outline: {
      control: 'boolean',
      description: 'Outlined button style',
    },
    noCaps: {
      control: 'boolean',
      description: 'Prevents text transformation to uppercase',
    },
    disable: {
      control: 'boolean',
      description: 'Disabled state',
    },
  },
  args: {
    color: 'accent',
    size: 'md',
    label: 'Button',
    unelevated: true,
    noCaps: true,
  },
} satisfies Meta<typeof QBtn>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Interactive button that responds to controls.
 * Use the controls panel to change color, size, label, and other properties.
 */
export const Interactive: Story = {
  args: {
    color: 'accent',
    size: 'md',
    label: 'Interactive Button',
    unelevated: true,
    noCaps: true,
  },
  render: (args) => ({
    components: { QBtn },
    setup() {
      return { args };
    },
    template: `
      <div class="q-pa-md q-gutter-md">
        <q-btn
          v-bind="args"
          class="text-weight-medium"
        />
      </div>
    `,
  }),
};

export const Primary: Story = {
  render: () => ({
    components: { QBtn },
    template: `
      <div class="q-pa-md q-gutter-md">
        <q-btn
          color="accent"
          label="Primary Button"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
        />
      </div>
    `,
  }),
};

export const PrimaryWithIcon: Story = {
  render: () => ({
    components: { QBtn },
    template: `


        <div class="q-pa-md q-gutter-md">

          <q-btn
            icon="o_add_circle"
            color="accent"
            label="Add Item"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
          />

        </div>

    `,
  }),
};

export const Secondary: Story = {
  render: () => ({
    components: { QBtn },
    template: `
      <div class="q-pa-md q-gutter-md">
        <q-btn
          outline
          color="grey-4"
          text-color="primary"
          label="Secondary button"
          unelevated
          no-caps
          size="md"
          class="text-weight-medium"
        />
      
      </div>
    `,
  }),
};

export const SecondaryWithIcon: Story = {
  render: () => ({
    components: { QBtn },
    template: `
      <div class="q-pa-md q-gutter-md">

          <q-btn
            outline
            color="grey-4"
            text-color="primary"
            icon="o_article"
            label="Documentation"
            unelevated
            no-caps
            size="md"
            class="text-weight-medium"
          />
      
      </div>
    `,
  }),
};

export const Sizes: Story = {
  render: () => ({
    components: { QBtn },
    template: `
      <div class="q-pa-md q-gutter-md column">
        <div class="row q-gutter-md items-center">
          <span class="text-body2 text-weight-medium" style="min-width: 100px;">Extra Small (xs):</span>
          <q-btn
            color="accent"
            size="xs"
            label="Extra Small"
            unelevated
            no-caps
            class="text-weight-medium"
          />
          <span class="text-caption text-grey-7">Used in timeline items, compact spaces</span>
        </div>
        <div class="row q-gutter-md items-center">
          <span class="text-body2 text-weight-medium" style="min-width: 100px;">Small (sm):</span>
          <q-btn
            color="accent"
            size="sm"
            label="Small"
            unelevated
            no-caps
            class="text-weight-medium"
          />
          <span class="text-caption text-grey-7">Used in tables, headers, secondary actions</span>
        </div>
        <div class="row q-gutter-md items-center">
          <span class="text-body2 text-weight-medium" style="min-width: 100px;">Medium (md):</span>
          <q-btn
            color="accent"
            size="md"
            label="Medium (Default)"
            unelevated
            no-caps
            class="text-weight-medium"
          />
          <span class="text-caption text-grey-7">Default for most primary actions</span>
        </div>
        <div class="row q-gutter-md items-center">
          <span class="text-body2 text-weight-medium" style="min-width: 100px;">Large (lg):</span>
          <q-btn
            color="accent"
            size="lg"
            label="Large"
            unelevated
            no-caps
            class="text-weight-medium"
          />
          <span class="text-caption text-grey-7">Used for prominent CTAs</span>
        </div>
      </div>
    `,
  }),
};
