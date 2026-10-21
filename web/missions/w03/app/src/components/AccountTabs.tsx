import type { Account } from '../types';

type Props = {
  accounts: Account[];
  selectedId: string;
  onSelect: (id: string) => void;
};

export function AccountTabs({ accounts, selectedId, onSelect }: Props) {
  return (
    <div role="tablist" aria-label="통장">
      {accounts.map((account) => (
        <button
          key={account.id}
          type="button"
          role="tab"
          aria-selected={account.id === selectedId}
          onClick={() => onSelect(account.id)}
        >
          {account.name}
        </button>
      ))}
    </div>
  );
}
