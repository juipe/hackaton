import { Users } from "lucide-react";
import { Link } from "react-router-dom";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";

const STEPS = [
  {
    title: "Создайте группу",
    description: "Назовите её и позовите тех, с кем делите расходы.",
  },
  {
    title: "Добавляйте расходы",
    description: "Делите поровну, точными суммами, процентами или долями.",
  },
  {
    title: "Закройте долги",
    description: "Видно, кто кому и сколько должен; перевод записывается в одно действие.",
  },
];

export function FirstRunCard({ firstName }: { firstName?: string }) {
  return (
    <Card className="p-5 sm:p-7 lg:p-8">
      <div className="grid gap-7 lg:grid-cols-[1.15fr_1fr] lg:gap-10">
        <div className="flex min-w-0 flex-col justify-center">
          <span className="flex size-[46px] items-center justify-center rounded-badge bg-accent text-accent-foreground">
            <Users className="size-[22px]" aria-hidden />
          </span>
          <h2 className="mt-5 text-[26px] font-bold leading-[1.15] tracking-[-0.025em] [overflow-wrap:anywhere] lg:text-[34px] lg:leading-10">
            {firstName ? `Добро пожаловать, ${firstName}` : "Добро пожаловать в Складчину"}
          </h2>
          <p className="mt-3 max-w-[52ch] text-base text-muted-foreground">
            Всё начинается с группы — квартира, поездка, ужин с друзьями. Создайте её, и
            каждый добавленный расход мы разделим, запомним и сведём к простому ответу:
            кто кому должен.
          </p>
          <div className="mt-7 flex flex-col gap-2.5 sm:flex-row">
            <Button asChild size="lg" className="w-full sm:w-auto">
              <Link to="/groups/new">Создать первую группу</Link>
            </Button>
            <Button asChild variant="secondary" size="lg" className="w-full sm:w-auto">
              <Link to="/groups">Мои группы</Link>
            </Button>
          </div>
          <p className="mt-4 text-[13px] text-dim">
            Вас уже пригласили? Откройте ссылку из приглашения — и вы окажетесь в группе.
          </p>
        </div>

        <ol className="flex flex-col gap-2 rounded-panel bg-subtle p-4 sm:p-5">
          {STEPS.map((step, index) => (
            <li key={step.title} className="flex gap-3.5 rounded-tile p-3">
              <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-bold text-accent-foreground">
                {index + 1}
              </span>
              <span className="min-w-0">
                <span className="block text-[15px] font-semibold">{step.title}</span>
                <span className="mt-1 block text-sm text-muted-foreground">
                  {step.description}
                </span>
              </span>
            </li>
          ))}
        </ol>
      </div>
    </Card>
  );
}
