"""Reference solutions for every built-in problem in youtopia/templates.yaml.

tests/test_templates.py runs each template's hidden tests against these, so a wrong
expected value in the library fails CI. One function per template, named as in the
template's `function` field.
"""

import bisect
import heapq
import math
from collections import Counter, defaultdict, deque

# --- labour ------------------------------------------------------------------------


def longest_streak(days):
    best = run = 0
    for day in days:
        run = run + 1 if day == 1 else 0
        best = max(best, run)
    return best


def move_empty_pallets(slots):
    full = [s for s in slots if s != 0]
    return full + [0] * (len(slots) - len(full))


def balance_point(weights):
    total, left = sum(weights), 0
    for i, weight in enumerate(weights):
        if left == total - left - weight:
            return i
        left += weight
    return -1


def rotate_shift(crew, k):
    if not crew:
        return []
    k %= len(crew)
    return crew[-k:] + crew[:-k] if k else list(crew)


def max_load_window(loads, k):
    window = best = sum(loads[:k])
    for i in range(k, len(loads)):
        window += loads[i] - loads[i - k]
        best = max(best, window)
    return best


def merge_shifts(shifts):
    merged = []
    for start, end in sorted(shifts):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def min_trips(crates, limit):
    crates = sorted(crates)
    i, j, trips = 0, len(crates) - 1, 0
    while i <= j:
        if crates[i] + crates[j] <= limit:
            i += 1
        j -= 1
        trips += 1
    return trips


def ways_to_cover(n):
    ways = [1, 1, 2]
    for _ in range(3, n + 1):
        ways.append(ways[-1] + ways[-2] + ways[-3])
    return ways[n]


def yard_puddles(heights):
    left, right = 0, len(heights) - 1
    left_max = right_max = water = 0
    while left < right:
        if heights[left] < heights[right]:
            left_max = max(left_max, heights[left])
            water += left_max - heights[left]
            left += 1
        else:
            right_max = max(right_max, heights[right])
            water += right_max - heights[right]
            right -= 1
    return water


def biggest_banner(boards):
    stack, best = [], 0
    for i, height in enumerate([*boards, 0]):
        start = i
        while stack and stack[-1][1] >= height:
            start, top = stack.pop()
            best = max(best, top * (i - start))
        stack.append((start, height))
    return best


# --- production ----------------------------------------------------------------------


def word_count(text):
    return len(text.split())


def reverse_title(title):
    return " ".join(reversed(title.split()))


def is_palindrome_line(line):
    chars = [c.lower() for c in line if c.isalnum()]
    return chars == chars[::-1]


def is_remix(a, b):
    return sorted(a) == sorted(b)


def longest_fresh_run(draft):
    seen, start, best = {}, 0, 0
    for i, c in enumerate(draft):
        if seen.get(c, -1) >= start:
            start = seen[c] + 1
        seen[c] = i
        best = max(best, i - start + 1)
    return best


def compress_draft(text):
    out, i = [], 0
    while i < len(text):
        j = i
        while j < len(text) and text[j] == text[i]:
            j += 1
        out.append(f"{text[i]}{j - i}")
        i = j
    return "".join(out)


def wrap_words(words, width):
    lines, line = [], []
    for word in words:
        if line and len(" ".join([*line, word])) > width:
            lines.append(" ".join(line))
            line = [word]
        else:
            line.append(word)
    if line:
        lines.append(" ".join(line))
    return lines


def longest_mirror(text):
    best = ""
    for center in range(len(text)):
        for lo, hi in ((center, center), (center, center + 1)):
            while lo >= 0 and hi < len(text) and text[lo] == text[hi]:
                lo, hi = lo - 1, hi + 1
            if hi - lo - 1 > len(best):
                best = text[lo + 1 : hi]
    return best


def edit_distance(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def shortest_excerpt(text, letters):
    need, missing, best, left = Counter(letters), len(letters), "", 0
    for right, c in enumerate(text, 1):
        if need[c] > 0:
            missing -= 1
        need[c] -= 1
        if missing == 0:
            while need[text[left]] < 0:
                need[text[left]] += 1
                left += 1
            if not best or right - left < len(best):
                best = text[left:right]
            need[text[left]] += 1
            missing += 1
            left += 1
    return best


# --- chores --------------------------------------------------------------------------


def sock_pairs(socks):
    return sum(count // 2 for count in Counter(socks).values())


def missing_spoon(spoons):
    n = len(spoons)
    return n * (n + 1) // 2 - sum(spoons)


def sort_laundry(loads):
    return sorted(loads)


def first_repeat(items):
    seen = set()
    for item in items:
        if item in seen:
            return item
        seen.add(item)
    return None


def chore_rota(chores, cooldown):
    counts = Counter(chores).values()
    top = max(counts)
    tied = sum(1 for c in counts if c == top)
    return max(len(chores), (top - 1) * (cooldown + 1) + tied)


def machines_needed(loads):
    ends = []
    for start, end in sorted(loads):
        if ends and ends[0] <= start:
            heapq.heapreplace(ends, end)
        else:
            heapq.heappush(ends, end)
    return len(ends)


def _flood(grid, r, c, seen, mark):
    rows, cols = len(grid), len(grid[0])
    stack, size = [(r, c)], 0
    seen.add((r, c))
    while stack:
        y, x = stack.pop()
        size += 1
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if (
                0 <= ny < rows and 0 <= nx < cols
                and grid[ny][nx] == mark and (ny, nx) not in seen
            ):  # fmt: skip
                seen.add((ny, nx))
                stack.append((ny, nx))
    return size


def messy_rooms(grid):
    seen, count = set(), 0
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell == "#" and (r, c) not in seen:
                _flood(grid, r, c, seen, "#")
                count += 1
    return count


def can_finish_chores(n, before):
    indegree, after = [0] * n, [[] for _ in range(n)]
    for a, b in before:
        after[a].append(b)
        indegree[b] += 1
    ready = [i for i in range(n) if indegree[i] == 0]
    done = 0
    while ready:
        i = ready.pop()
        done += 1
        for j in after[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                ready.append(j)
    return done == n


def minutes_to_tidy(grid):
    rows, cols = len(grid), len(grid[0]) if grid else 0
    frontier = [(r, c) for r in range(rows) for c in range(cols) if grid[r][c] == "T"]
    messy = sum(row.count("M") for row in grid)
    tidy, minutes = set(frontier), 0
    while frontier and messy:
        nxt = []
        for y, x in frontier:
            for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
                if (
                    0 <= ny < rows and 0 <= nx < cols
                    and grid[ny][nx] == "M" and (ny, nx) not in tidy
                ):  # fmt: skip
                    tidy.add((ny, nx))
                    nxt.append((ny, nx))
                    messy -= 1
        frontier, minutes = nxt, minutes + 1
    return minutes if messy == 0 else -1


def fewest_moves(grid):
    rows, cols = len(grid), len(grid[0])
    if grid[0][0] == "#" or grid[-1][-1] == "#":
        return -1
    dist, queue = {(0, 0): 0}, deque([(0, 0)])
    while queue:
        y, x = queue.popleft()
        if (y, x) == (rows - 1, cols - 1):
            return dist[(y, x)]
        for ny, nx in ((y + 1, x), (y - 1, x), (y, x + 1), (y, x - 1)):
            if 0 <= ny < rows and 0 <= nx < cols and grid[ny][nx] == "." and (ny, nx) not in dist:
                dist[(ny, nx)] = dist[(y, x)] + 1
                queue.append((ny, nx))
    return -1


# --- outreach ------------------------------------------------------------------------


def top_sender(senders):
    counts = Counter(senders)
    return min(counts, key=lambda s: (-counts[s], s))


def unique_contacts(contacts):
    return list(dict.fromkeys(contacts))


def balanced_brackets(message):
    pairs, stack = {")": "(", "]": "[", "}": "{"}, []
    for c in message:
        if c in "([{":
            stack.append(c)
        elif c in pairs and (not stack or stack.pop() != pairs[c]):
            return False
    return not stack


def free_pair(free, target):
    seen = {}
    for i, minutes in enumerate(free):
        if target - minutes in seen:
            return [seen[target - minutes], i]
        seen.setdefault(minutes, i)
    return []


def top_contacts(names, k):
    counts = Counter(names)
    return sorted(counts, key=lambda n: (-counts[n], n))[:k]


def friend_groups(links):
    n, seen, groups = len(links), set(), 0
    for i in range(n):
        if i in seen:
            continue
        groups += 1
        stack = [i]
        seen.add(i)
        while stack:
            a = stack.pop()
            for b in range(n):
                if links[a][b] and b not in seen:
                    seen.add(b)
                    stack.append(b)
    return groups


def degrees_apart(friendships, a, b):
    if a == b:
        return 0
    graph = defaultdict(set)
    for x, y in friendships:
        graph[x].add(y)
        graph[y].add(x)
    dist, queue = {a: 0}, deque([a])
    while queue:
        person = queue.popleft()
        for friend in graph[person]:
            if friend not in dist:
                dist[friend] = dist[person] + 1
                if friend == b:
                    return dist[friend]
                queue.append(friend)
    return -1


def merge_call_logs(logs):
    return list(heapq.merge(*logs))


def phone_tree(n, calls, start):
    graph = [[] for _ in range(n)]
    for u, v, minutes in calls:
        graph[u].append((v, minutes))
    dist, heap = {}, [(0, start)]
    while heap:
        d, u = heapq.heappop(heap)
        if u in dist:
            continue
        dist[u] = d
        for v, minutes in graph[u]:
            if v not in dist:
                heapq.heappush(heap, (d + minutes, v))
    return max(dist.values()) if len(dist) == n else -1


def message_hops(start, goal, words):
    vocabulary = set(words)
    if goal not in vocabulary:
        return 0
    queue, seen = deque([(start, 1)]), {start}
    while queue:
        word, steps = queue.popleft()
        if word == goal:
            return steps
        for i in range(len(word)):
            for ch in "abcdefghijklmnopqrstuvwxyz":
                candidate = word[:i] + ch + word[i + 1 :]
                if candidate in vocabulary and candidate not in seen:
                    seen.add(candidate)
                    queue.append((candidate, steps + 1))
    return 0


# --- training ------------------------------------------------------------------------


def flashcard_score(answers, key):
    return sum(a == k for a, k in zip(answers, key, strict=True))


def fizz_drill(n):
    return [
        "FizzBuzz" if i % 15 == 0 else "Fizz" if i % 3 == 0 else "Buzz" if i % 5 == 0 else str(i)
        for i in range(1, n + 1)
    ]


def glossary_search(terms, target):
    lo, hi = 0, len(terms) - 1
    while lo <= hi:
        mid = (lo + hi) // 2
        if terms[mid] == target:
            return mid
        if terms[mid] < target:
            lo = mid + 1
        else:
            hi = mid - 1
    return -1


def merge_study_lists(a, b):
    return sorted(a + b)


def longest_study_run(days):
    present, best = set(days), 0
    for day in present:
        if day - 1 not in present:
            end = day
            while end + 1 in present:
                end += 1
            best = max(best, end - day + 1)
    return best


def kth_best_score(scores, k):
    return sorted(scores, reverse=True)[k - 1]


def longest_rising_scores(scores):
    tails = []
    for score in scores:
        i = bisect.bisect_left(tails, score)
        if i == len(tails):
            tails.append(score)
        else:
            tails[i] = score
    return len(tails)


def course_order(n, before):
    indegree, after = [0] * n, [[] for _ in range(n)]
    for a, b in before:
        after[a].append(b)
        indegree[b] += 1
    ready = [i for i in range(n) if indegree[i] == 0]
    heapq.heapify(ready)
    order = []
    while ready:
        i = heapq.heappop(ready)
        order.append(i)
        for j in after[i]:
            indegree[j] -= 1
            if indegree[j] == 0:
                heapq.heappush(ready, j)
    return order if len(order) == n else []


def fewest_lessons(lengths, minutes):
    best = [0] + [math.inf] * minutes
    for m in range(1, minutes + 1):
        for length in lengths:
            if length <= m:
                best[m] = min(best[m], best[m - length] + 1)
    return best[minutes] if best[minutes] != math.inf else -1


def shared_syllabus(a, b):
    prev = [0] * (len(b) + 1)
    for ca in a:
        cur = [0]
        for j, cb in enumerate(b, 1):
            cur.append(prev[j - 1] + 1 if ca == cb else max(prev[j], cur[j - 1]))
        prev = cur
    return prev[-1]


# --- caretaking ----------------------------------------------------------------------


def thirsty_plants(days_since, limit):
    return sum(days >= limit for days in days_since)


def busiest_feeding_day(meals):
    return meals.index(max(meals))


def watering_steps(plants, capacity):
    steps, water = 0, capacity
    for i, need in enumerate(plants):
        if water < need:
            steps += 2 * i
            water = capacity
        steps += 1
        water -= need
    return steps


def can_plant(bed, n):
    bed, count = list(bed), 0
    for i in range(len(bed)):
        free_left = i == 0 or bed[i - 1] == 0
        free_right = i == len(bed) - 1 or bed[i + 1] == 0
        if bed[i] == 0 and free_left and free_right:
            bed[i] = 1
            count += 1
    return count >= n


def days_until_warmer(temps):
    answer, stack = [0] * len(temps), []
    for i, t in enumerate(temps):
        while stack and temps[stack[-1]] < t:
            j = stack.pop()
            answer[j] = i - j
        stack.append(i)
    return answer


def best_spot(seats):
    people = [i for i, taken in enumerate(seats) if taken]
    best = max(people[0], len(seats) - 1 - people[-1])
    for a, b in zip(people, people[1:], strict=False):
        best = max(best, (b - a) // 2)
    return best


def largest_garden_bed(grid):
    seen, best = set(), 0
    for r, row in enumerate(grid):
        for c, cell in enumerate(row):
            if cell == "#" and (r, c) not in seen:
                best = max(best, _flood(grid, r, c, seen, "#"))
    return best


def can_hop_across(stones):
    reach = 0
    for i, hop in enumerate(stones):
        if i > reach:
            return False
        reach = max(reach, i + hop)
    return True


def fair_treats(ratings):
    treats = [1] * len(ratings)
    for i in range(1, len(ratings)):
        if ratings[i] > ratings[i - 1]:
            treats[i] = treats[i - 1] + 1
    for i in range(len(ratings) - 2, -1, -1):
        if ratings[i] > ratings[i + 1]:
            treats[i] = max(treats[i], treats[i + 1] + 1)
    return sum(treats)


def fewest_sprinklers(n, ranges):
    reach = [0] * (n + 1)
    for i, r in enumerate(ranges):
        lo = max(0, i - r)
        reach[lo] = max(reach[lo], min(n, i + r))
    sprinklers = end = far = 0
    for i in range(n + 1):
        if i > far:
            return -1
        far = max(far, reach[i])
        if i == end and i < n:
            if far <= i:
                return -1
            sprinklers += 1
            end = far
    return sprinklers


# --- tickets -------------------------------------------------------------------------


def digit_sum(n):
    return sum(int(d) for d in str(abs(n)))


def is_prime(n):
    if n < 2:
        return False
    i = 2
    while i * i <= n:
        if n % i == 0:
            return False
        i += 1
    return True


def to_fahrenheit(celsius):
    return [c * 9 / 5 + 32 for c in celsius]


def roman_to_int(numeral):
    values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
    total = 0
    for i, c in enumerate(numeral):
        if i + 1 < len(numeral) and values[numeral[i + 1]] > values[c]:
            total -= values[c]
        else:
            total += values[c]
    return total


def pascal_row(n):
    row = [1]
    for _ in range(n):
        row = [a + b for a, b in zip([0, *row], [*row, 0], strict=True)]
    return row


def valid_sudoku(board):
    seen = set()
    for r in range(9):
        for c in range(9):
            digit = board[r][c]
            if digit == ".":
                continue
            for key in (("row", r, digit), ("col", c, digit), ("box", r // 3, c // 3, digit)):
                if key in seen:
                    return False
                seen.add(key)
    return True


def count_primes(n):
    if n < 3:
        return 0
    sieve = bytearray([1]) * n
    sieve[0] = sieve[1] = 0
    for i in range(2, math.isqrt(n - 1) + 1):
        if sieve[i]:
            sieve[i * i :: i] = bytearray(len(range(i * i, n, i)))
    return sum(sieve)


def projectile_range(speed, angle):
    return speed**2 * math.sin(math.radians(2 * angle)) / 9.81


def dice_ways(k):
    ways = {0: 1}
    for _ in range(k):
        nxt = defaultdict(int)
        for total, count in ways.items():
            for face in range(1, 7):
                nxt[total + face] += count
        ways = nxt
    return [ways[t] for t in range(k, 6 * k + 1)]


def queens_count(n):
    def place(row, cols, diag1, diag2):
        if row == n:
            return 1
        total = 0
        for c in range(n):
            if c not in cols and row - c not in diag1 and row + c not in diag2:
                total += place(row + 1, cols | {c}, diag1 | {row - c}, diag2 | {row + c})
        return total

    return place(0, frozenset(), frozenset(), frozenset())
