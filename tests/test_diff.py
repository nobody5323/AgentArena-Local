from agentarena_local.gitops.diff import compute_diff_stats


def test_diff_metrics_count_files_and_lines() -> None:
    patch = """diff --git a/app.py b/app.py
index 111..222 100644
--- a/app.py
+++ b/app.py
@@ -1,2 +1,3 @@
-old
+new
+extra
 context
diff --git a/readme.md b/readme.md
--- a/readme.md
+++ b/readme.md
@@ -1 +1 @@
-before
+after
"""

    stats = compute_diff_stats(patch)

    assert stats.changed_files == ["app.py", "readme.md"]
    assert stats.added_lines == 3
    assert stats.deleted_lines == 2
    assert stats.total_diff_lines == 5
