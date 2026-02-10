import type { Meta, StoryObj } from '@storybook/vue3';
import Co2TimelineItem from './Co2TimelineItem.vue';
import { timelineItems } from 'src/constant/timelineItems';
import { MODULE_STATES } from 'src/constant/moduleStates';

/**
 * Co2TimelineItem displays a timeline item with:
 * - Module icon (from module-icon plugin)
 * - State indicator button
 * - Module name label button
 *
 * ## Features
 * - Three states: default, in-progress, validated
 * - Color changes based on state
 * - Selection state support
 * - Navigation via router link
 */
const meta = {
  title: 'Molecules/Co2TimelineItem',
  component: Co2TimelineItem,
  tags: ['autodocs'],
  argTypes: {
    currentState: {
      control: 'select',
      options: Object.values(MODULE_STATES),
      description: 'Current state of the module',
    },
    selected: {
      control: 'boolean',
      description: 'Whether the item is selected',
    },
  },
} satisfies Meta<typeof Co2TimelineItem>;

export default meta;
type Story = StoryObj<typeof meta>;

/**
 * Default timeline item with default state.
 */
export const Default: Story = {
  args: {
    item: timelineItems[0],
    currentState: MODULE_STATES.Default,
    selected: false,
    to: '/en/unit/2024/module/my-lab',
  },
};

/**
 * All timeline items displayed in a grid, showing one of each module icon.
 */
export const AllModuleIcons: Story = {
  args: {
    item: timelineItems[0],
    currentState: MODULE_STATES.Default,
    selected: false,
  },
  render: () => {
    return {
      components: { Co2TimelineItem },
      template: `
        <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 32px; padding: 24px;">
          <div v-for="item in timelineItems" :key="item.link" style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
            <Co2TimelineItem 
              :item="item" 
              :current-state="'default'"
              :to="'/en/unit/2024/module/' + item.link"
              :selected="false"
            />
          </div>
        </div>
      `,
      setup() {
        return { timelineItems };
      },
    };
  },
};

/**
 * State variants showing each timeline item in different states.
 */
export const StateVariants: Story = {
  args: {
    item: timelineItems[0],
    currentState: MODULE_STATES.Default,
    selected: false,
  },
  render: () => {
    const states = Object.values(MODULE_STATES);
    return {
      components: { Co2TimelineItem },
      template: `
        <div style="padding: 24px;">
          <div v-for="item in timelineItems" :key="item.link" style="display: flex; align-items: center; gap: 64px; margin-bottom: 32px; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="min-width: 200px; font-weight: 500;">{{ item.link }}</div>
            <div v-for="state in states" :key="state" style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
              <Co2TimelineItem 
                :item="item" 
                :current-state="state"
                :to="'/en/unit/2024/module/' + item.link"
                :selected="false"
              />
              <span style="font-size: 11px; color: #666;">{{ state }}</span>
            </div>
          </div>
        </div>
      `,
      setup() {
        return { timelineItems, states };
      },
    };
  },
};

/**
 * Selected state variants showing how items look when selected.
 */
export const SelectedVariants: Story = {
  args: {
    item: timelineItems[0],
    currentState: MODULE_STATES.Default,
    selected: false,
  },
  render: () => {
    const states = Object.values(MODULE_STATES);
    return {
      components: { Co2TimelineItem },
      template: `
        <div style="padding: 24px;">
          <div v-for="item in timelineItems" :key="item.link" style="display: flex; align-items: center; gap: 32px; margin-bottom: 32px; padding: 16px; border: 1px solid #e0e0e0; border-radius: 8px;">
            <div style="min-width: 200px; font-weight: 500;">{{ item.link }}</div>
            <div v-for="state in states" :key="state" style="display: flex; flex-direction: column; align-items: center; gap: 8px;">
              <Co2TimelineItem 
                :item="item" 
                :current-state="state"
                :to="'/en/unit/2024/module/' + item.link"
                :selected="true"
              />
              <span style="font-size: 11px; color: #666;">{{ state }} (selected)</span>
            </div>
          </div>
        </div>
      `,
      setup() {
        return { timelineItems, states };
      },
    };
  },
};
