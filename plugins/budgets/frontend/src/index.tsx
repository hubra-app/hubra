import { registerPlugin } from '@hubra/plugin-sdk'
import { BudgetsTab } from './BudgetsTab'
import translations from './translations.json'

registerPlugin({
  id: 'budgets',
  tabs: [
    {
      screen: 'finance',
      id: 'budgets',
      label: 'shell.nav.budgets',
      module: 'finance.budgets',
      perm: 'budgets.budgets.read',
      component: BudgetsTab,
    },
  ],
  translations,
})
