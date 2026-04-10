from definitions import get_public_task_catalog

tasks = get_public_task_catalog()
print(f"Total tasks: {len(tasks)}")

graded = [t for t in tasks if t.get("grader_enabled") and t.get("has_grader")]
print(f"Graded tasks: {len(graded)}")

for task in graded:
    print(f"  [OK] {task['id']} - grader_enabled: {task['grader_enabled']}")
