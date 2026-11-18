import { Baby, Briefcase, Library, Users, Wallet } from 'lucide-react';

/*
 * Top-level HR modules. Drives both the home page cards and the navbar tabs,
 * so a future module (e.g. annual budget) only needs a new entry here + a route.
 */
export const HR_MODULES = [
  {
    key: 'jobs',
    path: '/jobs',
    title: 'משרות ומועמדים',
    description:
      'ניהול משרות פתוחות, העלאת קורות חיים, חיפוש מועמדים גלובלי, ייצוא לאקסל ושליחת זימונים ומיילי דחייה ב-Outlook.',
    icon: Briefcase,
    accent: {
      icon: 'bg-blue-100 text-blue-600',
      ring: 'hover:border-blue-300 hover:shadow-blue-100',
      cta: 'text-blue-600',
    },
  },
  {
    key: 'talent-pool',
    path: '/talent-pool',
    title: 'מאגר מועמדים',
    description:
      'מאגר קורות חיים כללי שאינו משויך למשרה: העלאה ופענוח אוטומטי, הוספה ידנית, חיפוש וסינון, והתאמה חכמה של מועמדים למשרות פתוחות.',
    icon: Library,
    accent: {
      icon: 'bg-teal-100 text-teal-600',
      ring: 'hover:border-teal-300 hover:shadow-teal-100',
      cta: 'text-teal-600',
    },
  },
  {
    key: 'candidates',
    path: '/candidates',
    title: 'כל המועמדים',
    description:
      'כל מועמד פעם אחת – מכל המשרות וממאגר המועמדים: היסטוריית מועמדויות, סטטוס בכל משרה, ומי הביא אותו (חבר מביא חבר).',
    icon: Users,
    accent: {
      icon: 'bg-indigo-100 text-indigo-600',
      ring: 'hover:border-indigo-300 hover:shadow-indigo-100',
      cta: 'text-indigo-600',
    },
  },
  {
    key: 'maternity',
    path: '/maternity',
    title: 'מעקב חופשות לידה',
    description:
      'טבלת עובדות בחופשת לידה, תאריכי חזרה, משלוח מתנות, עדכון נוכחות והודעות מוכנות ל-Outlook ול-Teams.',
    icon: Baby,
    accent: {
      icon: 'bg-pink-100 text-pink-600',
      ring: 'hover:border-pink-300 hover:shadow-pink-100',
      cta: 'text-pink-600',
    },
  },
  {
    key: 'budgets',
    path: '/budgets',
    title: 'ניהול תקציב שנתי',
    description:
      'תקציב שנתי לפי שנים, וחלוקתו לחגים ולאירועים: תקציב מוקצה מול ביצוע בפועל, סטיות, סטטוס ויתרה פנויה.',
    icon: Wallet,
    accent: {
      icon: 'bg-amber-100 text-amber-600',
      ring: 'hover:border-amber-300 hover:shadow-amber-100',
      cta: 'text-amber-600',
    },
  },
];
