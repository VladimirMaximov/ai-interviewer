import { createDefaultConfiguration, newQuestion } from './api';

describe('cabinet interview configuration mapping', () => {
  test('creates the three ordered product blocks', () => {
    const value = createDefaultConfiguration();
    expect(value.blocks.map((block) => block.key)).toEqual([
      'hard_skills', 'soft_skills', 'work_experience',
    ]);
    expect(value.blocks.every((block) => block.questions.length === 1)).toBe(true);
  });

  test('coding questions retain code and spoken-answer configuration', () => {
    const question = newQuestion('coding');
    expect(question.kind).toBe('coding');
    expect(question.language).toBe('python');
    expect(question.time_limit_seconds).toBeNull();
  });
});
