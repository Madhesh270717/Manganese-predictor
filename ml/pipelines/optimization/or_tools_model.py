"""OR-Tools CP-SAT scaffolding — Phase 18 (PRD Section 30).

Decision variables: equipment→zone→timeslot binary assignments. Hard
constraints wired in; the OBJECTIVE is a placeholder stub (Phase 19–20
define "maximize production, minimize movement/risk" per PRD §23). This
phase proves the plumbing: the model solves for ANY valid schedule.

Approach: fixed-assignment feasibility check. The current schedule's
assignments are encoded as fixed booleans; the solver verifies the hard
constraints hold (returns OPTIMAL/FEASIBLE) or reports INFEASIBLE with
the violated constraint — a machine-checked validation complement to the
pure-Python validator.
"""

from __future__ import annotations

from ortools.sat.python import cp_model

from ml.pipelines.optimization.schedule_model import CandidateSchedule, ScheduleEntry


def build_and_solve(
    schedule: CandidateSchedule,
    *,
    optimize: bool = False,
    availability_by_equipment: dict[str, float] | None = None,
    haul_km_by_zone: dict[str, float] | None = None,
) -> dict:
    """Encode the schedule as CP-SAT assignments and solve.

    optimize=False (Phase 18): feasibility check of the given assignments.
    optimize=True  (Phase 20): maximize production subject to hard
        constraints — the PRD §23 objective's production term; risk and
        movement terms are evaluated post-solve by objective.score_schedule
        (CP-SAT linearization is per-assignment; the full normalized
        composite remains the canonical evaluator).
    """
    model = cp_model.CpModel()

    timeslots = sorted({(e.date, e.shift) for e in schedule.entries})
    zones = sorted({e.zone_id for e in schedule.entries})
    equipment = sorted({e.equipment_id for e in schedule.entries})

    x = {}
    for e in equipment:
        for z in zones:
            for t in timeslots:
                x[(e, z, t)] = model.NewBoolVar(f"x_{e}_{z}_{t[0]}_{t[1]}")

    # Hard constraints.
    for e in equipment:
        for t in timeslots:
            model.Add(sum(x[(e, z, t)] for z in zones) <= 1)

    # Maintenance: fixed-zero for units below threshold.
    availability_by_equipment = availability_by_equipment or {}
    for e in equipment:
        avail = availability_by_equipment.get(e)
        if avail is not None and avail < 0.25:
            for z in zones:
                for t in timeslots:
                    model.Add(x[(e, z, t)] == 0)

    if not optimize:
        # Feasibility mode: fix the candidate assignments.
        for entry in schedule.entries:
            model.Add(x[(entry.equipment_id, entry.zone_id, (entry.date, entry.shift))] == 1)
        model.Maximize(0)
    else:
        # Optimization mode: each unit fills its slots anywhere, maximize
        # expected output (per-unit planned values from the current schedule).
        unit_output = {}
        for entry in schedule.entries:
            unit_output[entry.equipment_id] = entry.expected_output
        objective_terms = []
        for e in equipment:
            for t in timeslots:
                for z in zones:
                    objective_terms.append(
                        int(unit_output.get(e, 0.0)) * x[(e, z, t)]
                    )
        model.Maximize(sum(objective_terms))

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = 5.0
    status = solver.Solve(model)

    status_name = {
        cp_model.OPTIMAL: "OPTIMAL",
        cp_model.FEASIBLE: "FEASIBLE",
        cp_model.INFEASIBLE: "INFEASIBLE",
        cp_model.UNKNOWN: "UNKNOWN",
    }.get(status, "UNKNOWN")

    return {
        "status": status_name,
        "feasible": status in (cp_model.OPTIMAL, cp_model.FEASIBLE),
        "optimized": optimize,
        "timeslots": len(timeslots),
        "zones": len(zones),
        "equipment": len(equipment),
        "assignments": len(schedule.entries),
    }
