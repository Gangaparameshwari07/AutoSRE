from environment import AutoSREEnv
from server.graders import EasyGrader, MediumGrader, HardGrader, RecoveryGrader, EdgeGrader

env = AutoSREEnv()

tasks = [
    ("task_1_easy", EasyGrader()),
    ("task_2_medium", MediumGrader()),
    ("task_3_hard", HardGrader()),
    ("task_4_recovery", RecoveryGrader()),
    ("task_5_edge_database_crash", EdgeGrader())
]

for task_id, grader in tasks:
    obs = env.reset(task_id)
    score = grader.grade(obs)
    print(f"{task_id}: {score}")