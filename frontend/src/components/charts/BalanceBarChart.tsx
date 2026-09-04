import { Scale } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  ReferenceLine,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";

import { ChartFrame } from "@/components/charts/ChartFrame";
import {
  ChartTooltipCard,
  ChartTooltipRow,
  type ChartTooltipProps,
} from "@/components/charts/ChartTooltipCard";
import { truncate } from "@/lib/format";
import { balanceToneClass, formatCompact, formatSigned } from "@/lib/money";
import type { UserBalance, Uuid } from "@/types/api";

/**
 * The only chart allowed the balance hues. Brand green belongs to primary actions,
 * so it is never the sign of a number: here the sign *is* the meaning, and the bar
 * must read the same way as every balance figure in the app. These pull the very
 * tokens `balanceToneClass` paints with — `--positive` / `--negative`.
 */
const POSITIVE_FILL = "hsl(var(--positive))";
const NEGATIVE_FILL = "hsl(var(--negative))";

interface BalanceRow {
  user_id: Uuid;
  name: string;
  net_cents: number;
}

function BalanceTooltip({
  active,
  payload,
  currency,
}: ChartTooltipProps<BalanceRow> & { currency: string }) {
  const row = active ? payload?.[0]?.payload : undefined;
  if (!row) return null;
  const net = row.net_cents;
  return (
    <ChartTooltipCard title={row.name}>
      <ChartTooltipRow
        color={net < 0 ? NEGATIVE_FILL : POSITIVE_FILL}
        label="Баланс"
        value={formatSigned(net, currency)}
        valueClassName={balanceToneClass(net)}
      />
      <p className="text-[13px] text-dim">
        {net > 0 ? "Группа должна" : net < 0 ? "Долг перед группой" : "Расчёты закрыты"}
      </p>
    </ChartTooltipCard>
  );
}

export function BalanceBarChart({
  balances,
  currency,
  currentUserId,
  isLoading,
  className,
}: {
  balances?: UserBalance[];
  currency: string;
  currentUserId: string;
  isLoading?: boolean;
  className?: string;
}) {
  const rows: BalanceRow[] = (balances ?? [])
    .map((balance) => ({
      user_id: balance.user_id,
      name: balance.user_id === currentUserId ? "Вы" : balance.user.name,
      net_cents: balance.net_cents,
    }))
    .sort((a, b) => b.net_cents - a.net_cents);

  return (
    <ChartFrame
      isLoading={isLoading}
      isEmpty={rows.length === 0}
      emptyIcon={Scale}
      emptyLabel="Балансов для графика пока нет."
      className={className}
    >
      <ResponsiveContainer width="100%" height="100%">
        <BarChart
          data={rows}
          layout="vertical"
          margin={{ top: 4, right: 12, bottom: 0, left: 0 }}
        >
          <CartesianGrid horizontal={false} strokeDasharray="3 3" />
          {/* Compact roubles are wider than plain digits, so the ticks need room. */}
          <XAxis
            type="number"
            tickLine={false}
            axisLine={false}
            tickMargin={8}
            tickCount={4}
            minTickGap={24}
            interval="preserveStartEnd"
            tickFormatter={(value: number) => formatCompact(Number(value), currency)}
          />
          <YAxis
            type="category"
            dataKey="name"
            width={88}
            tickLine={false}
            axisLine={false}
            tickFormatter={(value: string) => truncate(String(value), 12)}
          />
          <ReferenceLine x={0} />
          <Tooltip content={<BalanceTooltip currency={currency} />} cursor={{ fillOpacity: 1 }} />
          <Bar dataKey="net_cents" radius={6} maxBarSize={26}>
            {rows.map((row) => (
              <Cell
                key={row.user_id}
                fill={row.net_cents < 0 ? NEGATIVE_FILL : POSITIVE_FILL}
              />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </ChartFrame>
  );
}
