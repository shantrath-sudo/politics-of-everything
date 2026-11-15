import plistlib
from pathlib import Path


def test_sunday_delivery_launchd_job_is_scheduled_for_sunday_at_0900():
    root = Path(__file__).resolve().parents[1]
    plist_path = root / "launchd" / "com.politics-of-everything.delivery.plist.template"
    config = plistlib.loads(plist_path.read_bytes())
    interval = config["StartCalendarInterval"]
    assert interval["Weekday"] in (0, 7)
    assert interval["Hour"] == 9
    assert interval["Minute"] == 0
    assert config["EnvironmentVariables"]["TZ"] == "Asia/Kolkata"
