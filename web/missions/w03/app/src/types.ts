export type Account = {
  id: string;
  name: string;
};

export type Transaction = {
  id: string;
  /** YYYY-MM-DD */
  date: string;
  title: string;
  /** 원 단위. 출금은 음수 */
  amount: number;
};
