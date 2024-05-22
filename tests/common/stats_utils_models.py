"""
Copyright 2020-2024 AstreaTSS.
This file is part of the Realms Playerlist Bot.

The Realms Playerlist Bot is free software: you can redistribute it and/or modify it under
the terms of the GNU Affero General Public License as published by the Free Software Foundation,
either version 3 of the License, or (at your option) any later version.

The Realms Playerlist Bot is distributed in the hope that it will be useful, but WITHOUT ANY
WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR
PURPOSE. See the GNU Affero General Public License for more details.

You should have received a copy of the GNU Affero General Public License along with the Realms
Playerlist Bot. If not, see <https://www.gnu.org/licenses/>.
"""

import datetime

import common.stats_utils as stats_utils

__all__ = (
    "TEST_DATETIMES",
    "MINUTES_PER_DAY_RESULTS",
    "MINUTES_PER_HOUR_RESULTS",
    "TIMESPAN_MINUTES_PER_HOUR_RESULTS",
    "TIMESPAN_MINUTES_PER_DAY_OF_THE_WEEK_RESULTS",
    "CALC_LEADERBOARD_RESULTS",
)

TEST_DATETIMES = [
    stats_utils.GatherDatetimesReturn(
        xuid="3e2e2756-9bd1-4645-b01e-d0736c23a311",
        joined_at=datetime.datetime(
            2024, 5, 15, 22, 13, 2, 328000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 15, 22, 33, 3, 627000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="995d5d9b-ccdb-4662-b226-306c3a2213e7",
        joined_at=datetime.datetime(
            2024, 5, 17, 21, 13, 2, 806000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 21, 15, 2, 565000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5318fe03-cc76-461a-b442-18b1bb4fe55e",
        joined_at=datetime.datetime(2024, 5, 14, 6, 51, 2, 788000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 14, 7, 15, 1, 548000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="cdf719ae-77eb-4f55-931c-c862bf9040fa",
        joined_at=datetime.datetime(2024, 5, 18, 17, 4, 4, 70000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 18, 20, 22, 5, 681000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="2cbf76b6-734d-46ef-a6b4-99c6f9783972",
        joined_at=datetime.datetime(
            2024, 5, 20, 15, 40, 2, 520000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 15, 44, 3, 752000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="3e2e2756-9bd1-4645-b01e-d0736c23a311",
        joined_at=datetime.datetime(
            2024, 5, 15, 19, 15, 4, 655000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(2024, 5, 15, 20, 1, 3, 232000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="bb847310-9c92-45df-a2f1-d8ee989bc680",
        joined_at=datetime.datetime(
            2024, 5, 19, 19, 19, 5, 862000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 19, 25, 3, 956000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="93d9fc92-f1bb-470d-88f5-553fc3eaa399",
        joined_at=datetime.datetime(2024, 5, 18, 1, 37, 3, 952000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 18, 1, 38, 2, 404000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f60bc45b-c290-4b47-96ff-487b1793a951",
        joined_at=datetime.datetime(
            2024, 5, 19, 23, 34, 3, 999000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 23, 37, 3, 404000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="a5745f75-98a8-4e13-b5ec-a9369949a958",
        joined_at=datetime.datetime(
            2024, 5, 17, 22, 22, 2, 556000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 22, 32, 2, 770000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="22b61f57-4a3a-4754-9965-2e75d5644511",
        joined_at=datetime.datetime(
            2024, 5, 18, 22, 54, 7, 428000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 22, 54, 7, 428000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f80784d3-e524-42c4-9722-8fb69fa03933",
        joined_at=datetime.datetime(
            2024, 5, 20, 22, 34, 5, 492000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(2024, 5, 20, 23, 55, 4, 14000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="8ee00965-217c-4275-b140-15513192e4b0",
        joined_at=datetime.datetime(
            2024, 5, 20, 16, 24, 2, 313000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 16, 25, 2, 500000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="ca90a9e3-ec16-461c-b462-930ef414010a",
        joined_at=datetime.datetime(
            2024, 5, 19, 14, 32, 2, 477000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 14, 32, 2, 477000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4341f8f3-48ba-49ac-a0c7-407590cfd9ff",
        joined_at=datetime.datetime(
            2024, 5, 14, 19, 30, 2, 502000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 14, 19, 41, 2, 278000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="1852a549-3c85-43d8-a01a-8e1988c6ebd0",
        joined_at=datetime.datetime(2024, 5, 19, 6, 38, 2, 881000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 7, 54, 1, 890000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4baf16bc-2130-483e-a576-42ae6f151aee",
        joined_at=datetime.datetime(
            2024, 5, 17, 17, 23, 2, 774000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 17, 37, 2, 768000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5cbfe0b3-b2c0-4692-944d-89d9f31e2864",
        joined_at=datetime.datetime(
            2024, 5, 20, 20, 49, 3, 387000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 21, 24, 6, 585000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="2a8638cf-4461-408e-9f54-a0defa7b5e7f",
        joined_at=datetime.datetime(2024, 5, 20, 3, 34, 3, 668000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 3, 34, 3, 668000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="e65f497f-4f3e-425f-bd0b-e392e91ba500",
        joined_at=datetime.datetime(2024, 5, 15, 19, 9, 2, 639000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 15, 19, 11, 3, 47000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="0e371c18-088c-4a29-b1ed-8e8c5de3b3e1",
        joined_at=datetime.datetime(
            2024, 5, 17, 15, 34, 2, 804000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 15, 34, 2, 804000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="9c47ed5b-527e-4405-b027-ed9f1d220738",
        joined_at=datetime.datetime(2024, 5, 20, 17, 52, 4, 35000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 18, 5, 3, 897000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="1e966065-0ea6-41b7-809c-900a28a84354",
        joined_at=datetime.datetime(2024, 5, 21, 0, 31, 3, 698000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 21, 0, 35, 5, 58000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="3e9468c1-fd7a-43ec-a625-140a8db9e951",
        joined_at=datetime.datetime(
            2024, 5, 20, 21, 28, 3, 697000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(2024, 5, 20, 22, 2, 5, 243000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="1866982c-43c4-48ad-bf55-6c87434a2ff2",
        joined_at=datetime.datetime(
            2024, 5, 16, 17, 22, 2, 445000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 16, 17, 22, 2, 445000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="596c8549-440c-461e-8de4-80b910ef562e",
        joined_at=datetime.datetime(2024, 5, 19, 21, 1, 3, 700000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 19, 21, 13, 3, 906000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="b229a4e7-50bd-4fd8-8d9c-4bc71928dbda",
        joined_at=datetime.datetime(2024, 5, 20, 5, 16, 1, 730000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 5, 18, 1, 991000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="d87367e7-bc49-4444-a5ce-b56cfc94fcee",
        joined_at=datetime.datetime(
            2024, 5, 16, 17, 48, 2, 142000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 16, 17, 53, 2, 153000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f545661f-6057-413a-9bf3-877eeb0277bc",
        joined_at=datetime.datetime(
            2024, 5, 19, 20, 12, 3, 346000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 20, 13, 3, 479000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="68c38763-793d-4961-9701-b0040158c987",
        joined_at=datetime.datetime(2024, 5, 18, 23, 0, 7, 294000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 18, 23, 5, 5, 741000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="a224fda3-bcc3-4de0-8e3d-e372038cc2ea",
        joined_at=datetime.datetime(
            2024, 5, 19, 16, 57, 3, 306000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 16, 57, 3, 306000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="554ea4a0-8d1b-43a3-bc5a-ee79e84e1e78",
        joined_at=datetime.datetime(2024, 5, 20, 1, 25, 2, 996000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 1, 25, 2, 996000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="09d58c42-1525-40da-a1e6-9641a4f9853b",
        joined_at=datetime.datetime(
            2024, 5, 19, 19, 37, 3, 587000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 19, 40, 4, 309000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="0817c59a-8af2-4dcd-9d82-8c04b6b49ccd",
        joined_at=datetime.datetime(
            2024, 5, 19, 11, 19, 1, 844000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 11, 20, 1, 797000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="94e10b13-f4c2-4906-9659-c1f19df40ab3",
        joined_at=datetime.datetime(
            2024, 5, 20, 19, 29, 3, 540000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 19, 35, 4, 135000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4341f8f3-48ba-49ac-a0c7-407590cfd9ff",
        joined_at=datetime.datetime(2024, 5, 16, 1, 3, 2, 447000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 16, 1, 43, 2, 525000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5cbfe0b3-b2c0-4692-944d-89d9f31e2864",
        joined_at=datetime.datetime(
            2024, 5, 14, 23, 44, 3, 273000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(2024, 5, 15, 0, 0, 3, 259000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="619e9ec9-5b3d-44e7-a665-df702ecfa4fc",
        joined_at=datetime.datetime(2024, 5, 19, 7, 58, 2, 213000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 8, 34, 3, 473000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="47409705-853b-43f3-9f3b-0567e00b117b",
        joined_at=datetime.datetime(2024, 5, 19, 23, 5, 5, 484000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 23, 6, 6, 71000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="b8829e00-1e3c-4ac5-b669-1050d514d0aa",
        joined_at=datetime.datetime(
            2024, 5, 16, 18, 28, 2, 440000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 16, 18, 32, 2, 533000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="a5745f75-98a8-4e13-b5ec-a9369949a958",
        joined_at=datetime.datetime(2024, 5, 19, 8, 9, 2, 427000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 8, 17, 2, 198000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="d533bc0a-6abe-4f60-a772-4bdd485e57e9",
        joined_at=datetime.datetime(2024, 5, 17, 2, 11, 2, 349000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 17, 2, 21, 2, 807000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="42a51430-d8cb-422c-9258-1151826bd9af",
        joined_at=datetime.datetime(
            2024, 5, 14, 22, 59, 2, 971000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(2024, 5, 14, 23, 2, 2, 746000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f5d4f04e-1283-46b0-9ead-5d7d62538173",
        joined_at=datetime.datetime(
            2024, 5, 17, 17, 29, 2, 578000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 17, 30, 3, 698000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="71a0e58d-5c19-4453-8a34-d0562b250b7e",
        joined_at=datetime.datetime(2024, 5, 14, 1, 42, 4, 585000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 14, 1, 42, 4, 585000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f0dd2688-f082-40b9-a32a-e19fd27acb0e",
        joined_at=datetime.datetime(2024, 5, 19, 10, 10, 2, 55000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 19, 10, 12, 1, 869000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="93d9fc92-f1bb-470d-88f5-553fc3eaa399",
        joined_at=datetime.datetime(
            2024, 5, 19, 23, 43, 4, 942000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 23, 43, 4, 942000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5af57a5b-efd1-4363-b729-adbd7471cf69",
        joined_at=datetime.datetime(
            2024, 5, 18, 19, 30, 3, 323000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 20, 11, 3, 793000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="554ea4a0-8d1b-43a3-bc5a-ee79e84e1e78",
        joined_at=datetime.datetime(
            2024, 5, 16, 14, 48, 1, 871000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(2024, 5, 16, 15, 29, 2, 92000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="93d9fc92-f1bb-470d-88f5-553fc3eaa399",
        joined_at=datetime.datetime(2024, 5, 21, 0, 26, 6, 110000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 21, 0, 34, 2, 875000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="d819670c-c4bd-404a-8690-ac8903c51389",
        joined_at=datetime.datetime(2024, 5, 20, 7, 6, 1, 862000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 7, 8, 1, 797000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="478eadfa-1495-4bcf-aa90-fd2098c61055",
        joined_at=datetime.datetime(2024, 5, 17, 21, 1, 4, 102000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 17, 22, 31, 3, 37000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="93d9fc92-f1bb-470d-88f5-553fc3eaa399",
        joined_at=datetime.datetime(2024, 5, 17, 0, 21, 3, 224000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 17, 0, 49, 3, 94000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5af57a5b-efd1-4363-b729-adbd7471cf69",
        joined_at=datetime.datetime(2024, 5, 19, 6, 27, 2, 455000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 6, 38, 2, 881000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="8c260e5f-6823-412e-895c-046f7d572c75",
        joined_at=datetime.datetime(2024, 5, 19, 0, 49, 5, 73000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 1, 4, 4, 905000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="ba5733f4-e7c5-467f-86d1-970b9f13a3b0",
        joined_at=datetime.datetime(2024, 5, 18, 3, 5, 3, 8000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 18, 3, 32, 3, 313000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="3904733e-fcc5-4753-bef2-a1565550eb49",
        joined_at=datetime.datetime(2024, 5, 17, 19, 2, 2, 332000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 17, 19, 22, 2, 796000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5cbfe0b3-b2c0-4692-944d-89d9f31e2864",
        joined_at=datetime.datetime(
            2024, 5, 15, 21, 50, 4, 497000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 15, 21, 52, 4, 149000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4f23370c-c8b3-43a8-96fe-a6e384198102",
        joined_at=datetime.datetime(
            2024, 5, 18, 22, 12, 53, 447000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 22, 24, 5, 156000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="d0029424-a4da-462c-9407-09aa5b24d60a",
        joined_at=datetime.datetime(
            2024, 5, 17, 19, 16, 6, 145000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 19, 24, 3, 588000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4421ff07-d0f0-4698-b2a5-5d6a9d410988",
        joined_at=datetime.datetime(2024, 5, 16, 1, 23, 2, 597000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 16, 1, 44, 2, 715000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="ecc4f5e8-407b-449f-9337-5adf97de90ad",
        joined_at=datetime.datetime(
            2024, 5, 18, 23, 41, 3, 293000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 23, 42, 5, 460000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5c77569a-c134-4fbc-ae5b-633028bc1d7a",
        joined_at=datetime.datetime(2024, 5, 15, 0, 6, 3, 245000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 15, 0, 58, 4, 318000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="7372e9c9-382a-453c-afcf-a95c4538282e",
        joined_at=datetime.datetime(
            2024, 5, 17, 23, 57, 2, 238000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 23, 57, 2, 238000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5af57a5b-efd1-4363-b729-adbd7471cf69",
        joined_at=datetime.datetime(
            2024, 5, 20, 23, 15, 3, 194000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 23, 20, 2, 902000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="bf6caab9-f426-455e-844c-54a3a7171895",
        joined_at=datetime.datetime(2024, 5, 18, 21, 5, 3, 437000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 18, 21, 39, 5, 116000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="fbe8006d-7122-4b76-b92f-8451ad2ea44b",
        joined_at=datetime.datetime(2024, 5, 18, 17, 7, 4, 850000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 18, 17, 7, 4, 850000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5d289fbf-e8ab-4ff3-9014-a0e6155028ba",
        joined_at=datetime.datetime(
            2024, 5, 17, 21, 19, 2, 997000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 21, 25, 2, 307000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="b0ca464a-cf07-46f8-8631-e42db912698a",
        joined_at=datetime.datetime(
            2024, 5, 18, 17, 53, 3, 278000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 18, 56, 5, 465000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="1866982c-43c4-48ad-bf55-6c87434a2ff2",
        joined_at=datetime.datetime(2024, 5, 16, 15, 52, 2, 96000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 16, 16, 5, 2, 190000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4341f8f3-48ba-49ac-a0c7-407590cfd9ff",
        joined_at=datetime.datetime(
            2024, 5, 16, 19, 27, 3, 199000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 16, 19, 27, 3, 494000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="97209b6b-62ee-49aa-bf3b-5d75fc87a981",
        joined_at=datetime.datetime(2024, 5, 14, 7, 30, 1, 542000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 14, 7, 30, 1, 542000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="40e498a0-efe7-44a9-a63a-1a0b9cf2e616",
        joined_at=datetime.datetime(2024, 5, 14, 21, 0, 2, 905000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 14, 21, 17, 6, 700000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="93d9fc92-f1bb-470d-88f5-553fc3eaa399",
        joined_at=datetime.datetime(
            2024, 5, 16, 17, 43, 2, 498000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 16, 18, 14, 2, 521000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f5e0ee56-8db5-4186-aa05-697be54614d9",
        joined_at=datetime.datetime(
            2024, 5, 19, 17, 23, 3, 745000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 17, 23, 3, 745000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4341f8f3-48ba-49ac-a0c7-407590cfd9ff",
        joined_at=datetime.datetime(2024, 5, 15, 20, 31, 3, 16000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 15, 20, 40, 4, 498000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="c0108913-05b2-4287-8a06-1f75966bf78f",
        joined_at=datetime.datetime(2024, 5, 15, 1, 6, 2, 587000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 15, 1, 26, 2, 550000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="3e9468c1-fd7a-43ec-a625-140a8db9e951",
        joined_at=datetime.datetime(
            2024, 5, 19, 19, 12, 2, 741000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 19, 16, 3, 744000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="941d6886-ab59-4256-b0d6-d3a7288c1419",
        joined_at=datetime.datetime(
            2024, 5, 18, 14, 39, 2, 331000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 14, 48, 4, 794000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="0817c59a-8af2-4dcd-9d82-8c04b6b49ccd",
        joined_at=datetime.datetime(2024, 5, 18, 14, 6, 2, 789000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 18, 14, 13, 2, 376000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="97209b6b-62ee-49aa-bf3b-5d75fc87a981",
        joined_at=datetime.datetime(2024, 5, 15, 4, 8, 2, 91000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 15, 4, 40, 1, 968000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="5cbfe0b3-b2c0-4692-944d-89d9f31e2864",
        joined_at=datetime.datetime(
            2024, 5, 18, 22, 24, 5, 156000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 23, 11, 5, 430000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="9010aa72-0da7-45df-8872-cf1752b3c297",
        joined_at=datetime.datetime(2024, 5, 20, 5, 48, 1, 606000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 5, 57, 1, 836000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4baf16bc-2130-483e-a576-42ae6f151aee",
        joined_at=datetime.datetime(
            2024, 5, 17, 17, 57, 2, 491000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 17, 17, 58, 2, 589000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4a6a6b4a-f5a3-467a-84e6-7bb5dd90180c",
        joined_at=datetime.datetime(
            2024, 5, 18, 14, 24, 5, 472000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 18, 14, 35, 3, 644000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="beda5b6c-efd9-47e9-97be-5bba9321b164",
        joined_at=datetime.datetime(
            2024, 5, 20, 23, 54, 3, 975000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 23, 54, 3, 975000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="b229a4e7-50bd-4fd8-8d9c-4bc71928dbda",
        joined_at=datetime.datetime(
            2024, 5, 19, 22, 31, 3, 801000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 22, 31, 3, 801000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="71b42f84-7306-4572-8d21-de4627ec77e3",
        joined_at=datetime.datetime(2024, 5, 20, 1, 56, 4, 998000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 1, 56, 4, 998000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="f259997f-addb-4c82-9807-ff256deefc19",
        joined_at=datetime.datetime(2024, 5, 19, 1, 2, 3, 732000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 19, 1, 3, 3, 736000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="208f3a1a-f867-4fc5-b67f-6160d3be91ae",
        joined_at=datetime.datetime(
            2024, 5, 15, 19, 23, 2, 595000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 15, 20, 32, 5, 467000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="2a8638cf-4461-408e-9f54-a0defa7b5e7f",
        joined_at=datetime.datetime(2024, 5, 20, 2, 34, 2, 353000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 20, 2, 34, 2, 353000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="cdb29742-12b7-4593-b7da-1d6c2aef1149",
        joined_at=datetime.datetime(2024, 5, 16, 15, 3, 1, 983000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 17, 0, 49, 3, 94000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4baf16bc-2130-483e-a576-42ae6f151aee",
        joined_at=datetime.datetime(2024, 5, 16, 19, 34, 3, 33000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(
            2024, 5, 16, 19, 57, 2, 676000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="e6444433-62b1-4253-ad32-3c082dd6c5b2",
        joined_at=datetime.datetime(2024, 5, 18, 2, 50, 2, 455000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 18, 2, 52, 3, 331000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="9270160f-fb92-46eb-beee-b4c387c6fed7",
        joined_at=datetime.datetime(
            2024, 5, 14, 20, 15, 2, 688000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 14, 20, 29, 6, 743000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4341f8f3-48ba-49ac-a0c7-407590cfd9ff",
        joined_at=datetime.datetime(2024, 5, 18, 5, 34, 2, 463000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 18, 5, 39, 2, 227000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="76dfba19-a56a-4e42-807b-1f181bee924e",
        joined_at=datetime.datetime(2024, 5, 15, 0, 10, 2, 869000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 15, 1, 3, 3, 599000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="9a40d65e-23ca-4e7e-abef-2ecc95654611",
        joined_at=datetime.datetime(2024, 5, 16, 2, 58, 2, 949000, tzinfo=datetime.UTC),
        last_seen=datetime.datetime(2024, 5, 16, 3, 5, 4, 262000, tzinfo=datetime.UTC),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="94c7bf48-9a14-4113-85bf-f35543d9f861",
        joined_at=datetime.datetime(
            2024, 5, 19, 12, 42, 2, 421000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 19, 12, 44, 1, 989000, tzinfo=datetime.UTC
        ),
    ),
    stats_utils.GatherDatetimesReturn(
        xuid="4224507d-d9ec-4419-a5c1-4ac487de860d",
        joined_at=datetime.datetime(
            2024, 5, 20, 21, 59, 4, 313000, tzinfo=datetime.UTC
        ),
        last_seen=datetime.datetime(
            2024, 5, 20, 22, 26, 3, 430000, tzinfo=datetime.UTC
        ),
    ),
]

MINUTES_PER_DAY_RESULTS: dict[datetime.datetime, int] = {
    datetime.datetime(2024, 5, 14, 0, 0, tzinfo=datetime.UTC): 85,
    datetime.datetime(2024, 5, 15, 0, 0, tzinfo=datetime.UTC): 305,
    datetime.datetime(2024, 5, 16, 0, 0, tzinfo=datetime.UTC): 771,
    datetime.datetime(2024, 5, 17, 0, 0, tzinfo=datetime.UTC): 239,
    datetime.datetime(2024, 5, 18, 0, 0, tzinfo=datetime.UTC): 463,
    datetime.datetime(2024, 5, 19, 0, 0, tzinfo=datetime.UTC): 182,
    datetime.datetime(2024, 5, 20, 0, 0, tzinfo=datetime.UTC): 219,
    datetime.datetime(2024, 5, 21, 0, 0, tzinfo=datetime.UTC): 12,
}

MINUTES_PER_HOUR_RESULTS: dict[datetime.datetime, int] = {
    datetime.datetime(2024, 5, 14, 6, 0, tzinfo=datetime.UTC): 24,
    datetime.datetime(2024, 5, 14, 7, 0, tzinfo=datetime.UTC): 15,
    datetime.datetime(2024, 5, 14, 8, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 10, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 11, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 12, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 14, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 15, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 16, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 17, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 18, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 14, 19, 0, tzinfo=datetime.UTC): 11,
    datetime.datetime(2024, 5, 14, 20, 0, tzinfo=datetime.UTC): 14,
    datetime.datetime(2024, 5, 14, 21, 0, tzinfo=datetime.UTC): 17,
    datetime.datetime(2024, 5, 14, 22, 0, tzinfo=datetime.UTC): 3,
    datetime.datetime(2024, 5, 14, 23, 0, tzinfo=datetime.UTC): 18,
    datetime.datetime(2024, 5, 15, 0, 0, tzinfo=datetime.UTC): 105,
    datetime.datetime(2024, 5, 15, 1, 0, tzinfo=datetime.UTC): 23,
    datetime.datetime(2024, 5, 15, 2, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 3, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 4, 0, tzinfo=datetime.UTC): 32,
    datetime.datetime(2024, 5, 15, 5, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 6, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 7, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 8, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 10, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 11, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 12, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 14, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 15, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 16, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 17, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 18, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 15, 19, 0, tzinfo=datetime.UTC): 85,
    datetime.datetime(2024, 5, 15, 20, 0, tzinfo=datetime.UTC): 42,
    datetime.datetime(2024, 5, 15, 21, 0, tzinfo=datetime.UTC): 2,
    datetime.datetime(2024, 5, 15, 22, 0, tzinfo=datetime.UTC): 20,
    datetime.datetime(2024, 5, 15, 23, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 0, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 1, 0, tzinfo=datetime.UTC): 61,
    datetime.datetime(2024, 5, 16, 2, 0, tzinfo=datetime.UTC): 7,
    datetime.datetime(2024, 5, 16, 3, 0, tzinfo=datetime.UTC): 5,
    datetime.datetime(2024, 5, 16, 4, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 5, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 6, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 7, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 8, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 10, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 11, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 12, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 16, 14, 0, tzinfo=datetime.UTC): 41,
    datetime.datetime(2024, 5, 16, 15, 0, tzinfo=datetime.UTC): 99,
    datetime.datetime(2024, 5, 16, 16, 0, tzinfo=datetime.UTC): 65,
    datetime.datetime(2024, 5, 16, 17, 0, tzinfo=datetime.UTC): 96,
    datetime.datetime(2024, 5, 16, 18, 0, tzinfo=datetime.UTC): 78,
    datetime.datetime(2024, 5, 16, 19, 0, tzinfo=datetime.UTC): 83,
    datetime.datetime(2024, 5, 16, 20, 0, tzinfo=datetime.UTC): 60,
    datetime.datetime(2024, 5, 16, 21, 0, tzinfo=datetime.UTC): 60,
    datetime.datetime(2024, 5, 16, 22, 0, tzinfo=datetime.UTC): 60,
    datetime.datetime(2024, 5, 16, 23, 0, tzinfo=datetime.UTC): 60,
    datetime.datetime(2024, 5, 17, 0, 0, tzinfo=datetime.UTC): 77,
    datetime.datetime(2024, 5, 17, 1, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 2, 0, tzinfo=datetime.UTC): 10,
    datetime.datetime(2024, 5, 17, 3, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 4, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 5, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 6, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 7, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 8, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 10, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 11, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 12, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 14, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 15, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 16, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 17, 0, tzinfo=datetime.UTC): 16,
    datetime.datetime(2024, 5, 17, 18, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 19, 0, tzinfo=datetime.UTC): 28,
    datetime.datetime(2024, 5, 17, 20, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 17, 21, 0, tzinfo=datetime.UTC): 67,
    datetime.datetime(2024, 5, 17, 22, 0, tzinfo=datetime.UTC): 41,
    datetime.datetime(2024, 5, 17, 23, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 0, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 1, 0, tzinfo=datetime.UTC): 1,
    datetime.datetime(2024, 5, 18, 2, 0, tzinfo=datetime.UTC): 2,
    datetime.datetime(2024, 5, 18, 3, 0, tzinfo=datetime.UTC): 27,
    datetime.datetime(2024, 5, 18, 4, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 5, 0, tzinfo=datetime.UTC): 5,
    datetime.datetime(2024, 5, 18, 6, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 7, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 8, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 10, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 11, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 12, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 14, 0, tzinfo=datetime.UTC): 27,
    datetime.datetime(2024, 5, 18, 15, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 16, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 18, 17, 0, tzinfo=datetime.UTC): 63,
    datetime.datetime(2024, 5, 18, 18, 0, tzinfo=datetime.UTC): 116,
    datetime.datetime(2024, 5, 18, 19, 0, tzinfo=datetime.UTC): 101,
    datetime.datetime(2024, 5, 18, 20, 0, tzinfo=datetime.UTC): 33,
    datetime.datetime(2024, 5, 18, 21, 0, tzinfo=datetime.UTC): 34,
    datetime.datetime(2024, 5, 18, 22, 0, tzinfo=datetime.UTC): 59,
    datetime.datetime(2024, 5, 18, 23, 0, tzinfo=datetime.UTC): 17,
    datetime.datetime(2024, 5, 19, 0, 0, tzinfo=datetime.UTC): 15,
    datetime.datetime(2024, 5, 19, 1, 0, tzinfo=datetime.UTC): 5,
    datetime.datetime(2024, 5, 19, 2, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 3, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 4, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 5, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 6, 0, tzinfo=datetime.UTC): 33,
    datetime.datetime(2024, 5, 19, 7, 0, tzinfo=datetime.UTC): 90,
    datetime.datetime(2024, 5, 19, 8, 0, tzinfo=datetime.UTC): 42,
    datetime.datetime(2024, 5, 19, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 10, 0, tzinfo=datetime.UTC): 2,
    datetime.datetime(2024, 5, 19, 11, 0, tzinfo=datetime.UTC): 1,
    datetime.datetime(2024, 5, 19, 12, 0, tzinfo=datetime.UTC): 2,
    datetime.datetime(2024, 5, 19, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 14, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 15, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 16, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 17, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 18, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 19, 0, tzinfo=datetime.UTC): 13,
    datetime.datetime(2024, 5, 19, 20, 0, tzinfo=datetime.UTC): 1,
    datetime.datetime(2024, 5, 19, 21, 0, tzinfo=datetime.UTC): 12,
    datetime.datetime(2024, 5, 19, 22, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 19, 23, 0, tzinfo=datetime.UTC): 4,
    datetime.datetime(2024, 5, 20, 0, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 1, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 2, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 3, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 4, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 5, 0, tzinfo=datetime.UTC): 11,
    datetime.datetime(2024, 5, 20, 6, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 7, 0, tzinfo=datetime.UTC): 2,
    datetime.datetime(2024, 5, 20, 8, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 9, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 10, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 11, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 12, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 13, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 14, 0, tzinfo=datetime.UTC): 0,
    datetime.datetime(2024, 5, 20, 15, 0, tzinfo=datetime.UTC): 4,
    datetime.datetime(2024, 5, 20, 16, 0, tzinfo=datetime.UTC): 1,
    datetime.datetime(2024, 5, 20, 17, 0, tzinfo=datetime.UTC): 13,
    datetime.datetime(2024, 5, 20, 18, 0, tzinfo=datetime.UTC): 5,
    datetime.datetime(2024, 5, 20, 19, 0, tzinfo=datetime.UTC): 6,
    datetime.datetime(2024, 5, 20, 20, 0, tzinfo=datetime.UTC): 35,
    datetime.datetime(2024, 5, 20, 21, 0, tzinfo=datetime.UTC): 85,
    datetime.datetime(2024, 5, 20, 22, 0, tzinfo=datetime.UTC): 54,
    datetime.datetime(2024, 5, 20, 23, 0, tzinfo=datetime.UTC): 60,
    datetime.datetime(2024, 5, 21, 0, 0, tzinfo=datetime.UTC): 12,
}

TIMESPAN_MINUTES_PER_HOUR_RESULTS: dict[datetime.time, int] = {
    datetime.time(0, 0): 209,
    datetime.time(1, 0): 90,
    datetime.time(2, 0): 19,
    datetime.time(3, 0): 32,
    datetime.time(4, 0): 32,
    datetime.time(5, 0): 16,
    datetime.time(6, 0): 57,
    datetime.time(7, 0): 107,
    datetime.time(8, 0): 42,
    datetime.time(9, 0): 0,
    datetime.time(10, 0): 2,
    datetime.time(11, 0): 1,
    datetime.time(12, 0): 2,
    datetime.time(13, 0): 0,
    datetime.time(14, 0): 68,
    datetime.time(15, 0): 103,
    datetime.time(16, 0): 66,
    datetime.time(17, 0): 188,
    datetime.time(18, 0): 199,
    datetime.time(19, 0): 327,
    datetime.time(20, 0): 185,
    datetime.time(21, 0): 277,
    datetime.time(22, 0): 237,
    datetime.time(23, 0): 159,
}

TIMESPAN_MINUTES_PER_DAY_OF_THE_WEEK_RESULTS: dict[datetime.date, int] = {
    datetime.date(1970, 1, 4): 182,
    datetime.date(1970, 1, 5): 219,
    datetime.date(1970, 1, 6): 97,
    datetime.date(1970, 1, 7): 305,
    datetime.date(1970, 1, 8): 771,
    datetime.date(1970, 1, 9): 239,
    datetime.date(1970, 1, 10): 463,
}

CALC_LEADERBOARD_RESULTS: list[tuple[str, int]] = [
    ("cdb29742-12b7-4593-b7da-1d6c2aef1149", 35160),
    ("cdf719ae-77eb-4f55-931c-c862bf9040fa", 11880),
    ("5cbfe0b3-b2c0-4692-944d-89d9f31e2864", 6000),
    ("478eadfa-1495-4bcf-aa90-fd2098c61055", 5400),
    ("f80784d3-e524-42c4-9722-8fb69fa03933", 4860),
    ("1852a549-3c85-43d8-a01a-8e1988c6ebd0", 4560),
    ("208f3a1a-f867-4fc5-b67f-6160d3be91ae", 4140),
    ("93d9fc92-f1bb-470d-88f5-553fc3eaa399", 4080),
    ("3e2e2756-9bd1-4645-b01e-d0736c23a311", 3960),
    ("4341f8f3-48ba-49ac-a0c7-407590cfd9ff", 3900),
    ("b0ca464a-cf07-46f8-8631-e42db912698a", 3780),
    ("5af57a5b-efd1-4363-b729-adbd7471cf69", 3420),
    ("76dfba19-a56a-4e42-807b-1f181bee924e", 3180),
    ("5c77569a-c134-4fbc-ae5b-633028bc1d7a", 3120),
    ("554ea4a0-8d1b-43a3-bc5a-ee79e84e1e78", 2460),
    ("4baf16bc-2130-483e-a576-42ae6f151aee", 2280),
    ("3e9468c1-fd7a-43ec-a625-140a8db9e951", 2280),
    ("619e9ec9-5b3d-44e7-a665-df702ecfa4fc", 2160),
    ("bf6caab9-f426-455e-844c-54a3a7171895", 2040),
    ("97209b6b-62ee-49aa-bf3b-5d75fc87a981", 1920),
    ("ba5733f4-e7c5-467f-86d1-970b9f13a3b0", 1620),
    ("4224507d-d9ec-4419-a5c1-4ac487de860d", 1620),
    ("5318fe03-cc76-461a-b442-18b1bb4fe55e", 1440),
    ("4421ff07-d0f0-4698-b2a5-5d6a9d410988", 1260),
    ("3904733e-fcc5-4753-bef2-a1565550eb49", 1200),
    ("c0108913-05b2-4287-8a06-1f75966bf78f", 1200),
    ("a5745f75-98a8-4e13-b5ec-a9369949a958", 1080),
    ("40e498a0-efe7-44a9-a63a-1a0b9cf2e616", 1020),
    ("8c260e5f-6823-412e-895c-046f7d572c75", 900),
    ("9270160f-fb92-46eb-beee-b4c387c6fed7", 840),
    ("9c47ed5b-527e-4405-b027-ed9f1d220738", 780),
    ("1866982c-43c4-48ad-bf55-6c87434a2ff2", 780),
    ("596c8549-440c-461e-8de4-80b910ef562e", 720),
    ("4f23370c-c8b3-43a8-96fe-a6e384198102", 720),
    ("4a6a6b4a-f5a3-467a-84e6-7bb5dd90180c", 660),
    ("d533bc0a-6abe-4f60-a772-4bdd485e57e9", 600),
    ("941d6886-ab59-4256-b0d6-d3a7288c1419", 540),
    ("9010aa72-0da7-45df-8872-cf1752b3c297", 540),
    ("0817c59a-8af2-4dcd-9d82-8c04b6b49ccd", 480),
    ("d0029424-a4da-462c-9407-09aa5b24d60a", 480),
    ("9a40d65e-23ca-4e7e-abef-2ecc95654611", 420),
    ("bb847310-9c92-45df-a2f1-d8ee989bc680", 360),
    ("94e10b13-f4c2-4906-9659-c1f19df40ab3", 360),
    ("5d289fbf-e8ab-4ff3-9014-a0e6155028ba", 360),
    ("d87367e7-bc49-4444-a5ce-b56cfc94fcee", 300),
    ("68c38763-793d-4961-9701-b0040158c987", 300),
    ("2cbf76b6-734d-46ef-a6b4-99c6f9783972", 240),
    ("1e966065-0ea6-41b7-809c-900a28a84354", 240),
    ("b8829e00-1e3c-4ac5-b669-1050d514d0aa", 240),
    ("f60bc45b-c290-4b47-96ff-487b1793a951", 180),
    ("09d58c42-1525-40da-a1e6-9641a4f9853b", 180),
    ("42a51430-d8cb-422c-9258-1151826bd9af", 180),
    ("995d5d9b-ccdb-4662-b226-306c3a2213e7", 120),
    ("e65f497f-4f3e-425f-bd0b-e392e91ba500", 120),
    ("b229a4e7-50bd-4fd8-8d9c-4bc71928dbda", 120),
    ("f0dd2688-f082-40b9-a32a-e19fd27acb0e", 120),
    ("d819670c-c4bd-404a-8690-ac8903c51389", 120),
    ("e6444433-62b1-4253-ad32-3c082dd6c5b2", 120),
    ("94c7bf48-9a14-4113-85bf-f35543d9f861", 120),
    ("8ee00965-217c-4275-b140-15513192e4b0", 60),
    ("f545661f-6057-413a-9bf3-877eeb0277bc", 60),
    ("47409705-853b-43f3-9f3b-0567e00b117b", 60),
    ("f5d4f04e-1283-46b0-9ead-5d7d62538173", 60),
    ("ecc4f5e8-407b-449f-9337-5adf97de90ad", 60),
    ("f259997f-addb-4c82-9807-ff256deefc19", 60),
]
