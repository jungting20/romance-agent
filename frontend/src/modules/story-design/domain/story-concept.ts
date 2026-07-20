export const TROPE_IDS = [
  "rivals-to-lovers",
  "contract-romance",
  "reunion",
  "friends-to-lovers",
] as const;

export type TropeId = (typeof TROPE_IDS)[number];

export interface TropeTemplate {
  id: TropeId;
  title: string;
  summary: string;
  tags: string[];
  starterLogline: string;
}

export function isTropeId(value: unknown): value is TropeId {
  return typeof value === "string" && TROPE_IDS.some((tropeId) => tropeId === value);
}

export const TROPE_TEMPLATES: TropeTemplate[] = [
  {
    id: "rivals-to-lovers",
    title: "앙숙에서 연인으로",
    summary: "부딪칠수록 선명해지는 마음",
    tags: ["긴장감", "티키타카", "느린 감정선"],
    starterLogline:
      "매번 승부를 겨루는 두 사람이 공동의 목표를 위해 손을 잡으며 서로의 진심을 발견한다.",
  },
  {
    id: "contract-romance",
    title: "계약 연애",
    summary: "거짓으로 시작한 관계의 진짜 감정",
    tags: ["가짜 연애", "가까운 거리", "비밀"],
    starterLogline:
      "서로의 필요 때문에 연인을 연기한 두 사람이 계약의 끝에서 진짜 마음을 마주한다.",
  },
  {
    id: "reunion",
    title: "재회 로맨스",
    summary: "끝내지 못한 사랑의 두 번째 기회",
    tags: ["과거", "오해", "두 번째 기회"],
    starterLogline:
      "오해로 헤어진 두 사람이 오래된 온실에서 다시 만나 미처 전하지 못한 진실을 마주한다.",
  },
  {
    id: "friends-to-lovers",
    title: "친구에서 연인으로",
    summary: "익숙한 사이에 번지는 낯선 설렘",
    tags: ["오랜 친구", "깨달음", "고백"],
    starterLogline:
      "오랜 친구였던 두 사람이 한 번의 약속을 계기로 서로를 새로운 눈으로 바라보기 시작한다.",
  },
];

export interface StoryConcept {
  id: string;
  projectId: string;
  tropeId: TropeId;
  logline: string;
  protagonistNames: [string, string];
}

export interface CreateStoryConceptInput extends Omit<
  StoryConcept,
  "tropeId" | "protagonistNames"
> {
  tropeId: string;
  protagonistNames: [string, string];
}

export function getTropeTemplate(tropeId: string): TropeTemplate {
  const trope = TROPE_TEMPLATES.find(({ id }) => id === tropeId);

  if (!trope) {
    throw new Error("선택한 로맨스 트로프를 찾을 수 없습니다.");
  }

  return trope;
}

export function createStoryConcept(input: CreateStoryConceptInput): StoryConcept {
  const trope = getTropeTemplate(input.tropeId);
  const protagonistNames = input.protagonistNames.map((name) => name.trim()) as [string, string];

  if (protagonistNames.some((name) => !name)) {
    throw new Error("두 주인공의 이름을 모두 입력해 주세요.");
  }

  return {
    ...input,
    tropeId: trope.id,
    logline: input.logline.trim(),
    protagonistNames,
  };
}
