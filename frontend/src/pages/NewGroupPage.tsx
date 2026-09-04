import { PageHeader } from "@/components/common/PageHeader";
import { SectionCard } from "@/components/common/SectionCard";
import { GroupForm } from "@/components/groups/GroupForm";

const NEXT_STEPS = [
  "Пригласите по электронной почте тех, с кем делите эти расходы.",
  "Добавляйте расходы и выбирайте, как делить каждый: поровну, точными суммами, процентами или долями.",
  "Рассчитывайтесь когда удобно — до этого «Складчина» ведёт текущий баланс.",
];

export default function NewGroupPage() {
  return (
    <div className="flex w-full max-w-[720px] flex-col gap-6">
      <PageHeader
        back={{ to: "/groups", label: "Группы" }}
        title="Новая группа"
        description="Назовите общий счёт, который будете вести вместе. Всё это можно изменить позже."
      />

      <SectionCard
        title="Данные группы"
        description="Чтобы начать, достаточно названия."
      >
        <GroupForm />
      </SectionCard>

      <SectionCard title="Что дальше" description="Три шага после создания группы.">
        <ol className="flex flex-col gap-3">
          {NEXT_STEPS.map((step, index) => (
            <li
              key={step}
              className="flex items-start gap-3.5 rounded-row bg-subtle px-[18px] py-3.5"
            >
              <span
                aria-hidden="true"
                className="flex size-7 shrink-0 items-center justify-center rounded-full bg-accent text-[13px] font-bold text-accent-foreground"
              >
                {index + 1}
              </span>
              <p className="text-[15px] leading-relaxed text-muted-foreground">{step}</p>
            </li>
          ))}
        </ol>
      </SectionCard>
    </div>
  );
}
