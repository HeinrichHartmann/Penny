import { SelectorHeader } from '../components/SelectorHeader.js';
import { TransactionsList } from './TransactionsList.js';

export const TransactionsView = {
  name: 'TransactionsView',
  components: {
    SelectorHeader,
    TransactionsList,
  },
  props: {
    model: { type: Object, required: true },
  },
  template: `
    <div>
      <h2 style="font-size: 1.4rem; margin-bottom: 20px;">Transactions</h2>

      <selector-header
        :state="model.selectorState"
        :actions="model.selectorActions"
      ></selector-header>

      <transactions-list :model="model"></transactions-list>
    </div>
  `,
};
