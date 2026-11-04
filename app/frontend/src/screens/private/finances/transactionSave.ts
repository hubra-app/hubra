import type { Transaction } from '@/types'
import type { TransactionCreate } from '@/api/finance'
import type { TransactionFormValues } from './TransactionFormModal'

/** What the transaction form sends to save a change to `before`. */
export function transactionUpdate(
  before: Transaction,
  values: TransactionFormValues,
): Partial<TransactionCreate> & { status?: 'Pending' | 'Completed' } {
  return {
    date: values.date,
    description: values.description,
    categoryId: values.categoryId,
    amount: values.amount,
    method: values.method,
    type: values.type,
    status: values.status,
    // Only send the name when it changed: an empty one would unlink nothing
    // but blank out a name the bank import set.
    ...(values.payeeName.trim() !== (before.payeeName ?? '')
      ? { payeeName: values.payeeName.trim() }
      : {}),
  }
}
