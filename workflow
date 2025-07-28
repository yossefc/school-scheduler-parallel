{
  "name": "Import Excel avec Cours Parallèles",
  "nodes": [
    {
      "parameters": {
        "functionCode": "// Analyser et séparer les cours individuels des cours parallèles\nconst teacherLoads = items[0].json.data.teacherSubjects || [];\n\n// Séparer en deux catégories\nconst individualLoads = [];\nconst parallelCandidates = {};\n\nfor (const load of teacherLoads) {\n  const classList = load.class_list || '';\n  \n  // Si plusieurs classes séparées par des virgules\n  if (classList.includes(',')) {\n    // C'est potentiellement un cours parallèle\n    const key = `${load.subject}_${load.grade}`;\n    \n    if (!parallelCandidates[key]) {\n      parallelCandidates[key] = [];\n    }\n    \n    parallelCandidates[key].push({\n      teacher_name: load.teacher_name,\n      subject: load.subject,\n      grade: String(load.grade),\n      class_list: classList,\n      hours: Number(load.hours) || 0\n    });\n  } else {\n    // Cours individuel (une seule classe ou pas de classe)\n    individualLoads.push({\n      teacher_name: load.teacher_name,\n      subject: load.subject,\n      grade: String(load.grade),\n      class_list: classList,\n      hours: Number(load.hours) || 0,\n      work_days: load.work_days || null\n    });\n  }\n}\n\n// Identifier les vrais groupes parallèles\nconst parallelGroups = [];\nconst remainingLoads = [];\n\nfor (const [key, candidates] of Object.entries(parallelCandidates)) {\n  if (candidates.length > 1) {\n    // C'est un vrai groupe parallèle\n    const [subject, grade] = key.split('_');\n    \n    parallelGroups.push({\n      subject,\n      grade,\n      teachers: candidates.map(c => c.teacher_name),\n      details: candidates\n    });\n  } else {\n    // Pas vraiment parallèle, juste un prof avec plusieurs classes\n    remainingLoads.push(candidates[0]);\n  }\n}\n\n// Retourner les résultats séparés\nreturn [{\n  json: {\n    individualLoads: [...individualLoads, ...remainingLoads],\n    parallelGroups: parallelGroups,\n    stats: {\n      totalLoads: teacherLoads.length,\n      individual: individualLoads.length + remainingLoads.length,\n      parallelGroups: parallelGroups.length\n    }\n  }\n}];"
      },
      "name": "Analyser Cours Parallèles",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [600, 200],
      "id": "analyze-parallel"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "-- Nettoyer les tables avant import\nTRUNCATE TABLE teacher_load CASCADE;\nTRUNCATE TABLE parallel_groups CASCADE;\nTRUNCATE TABLE parallel_teaching_details CASCADE;"
      },
      "name": "Nettoyer Tables",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [800, 200],
      "id": "clean-tables"
    },
    {
      "parameters": {
        "functionCode": "// Préparer les charges individuelles pour insertion\nconst loads = items[0].json.individualLoads || [];\n\nreturn loads.map(load => ({\n  json: {\n    teacher_name: load.teacher_name,\n    subject: load.subject,\n    grade: load.grade,\n    class_list: load.class_list,\n    hours: load.hours,\n    work_days: load.work_days,\n    is_parallel: false  // Marquer explicitement comme non-parallèle\n  }\n}));"
      },
      "name": "Format Individual Loads",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [1000, 100],
      "id": "format-individual"
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "teacher_load",
        "columns": {
          "mappingMode": "defineBelow",
          "value": {
            "teacher_name": "={{ $json.teacher_name }}",
            "subject": "={{ $json.subject }}",
            "grade": "={{ $json.grade }}",
            "class_list": "={{ $json.class_list }}",
            "hours": "={{ $json.hours }}",
            "work_days": "={{ $json.work_days }}",
            "is_parallel": "={{ $json.is_parallel }}"
          }
        }
      },
      "name": "Insert Individual Loads",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [1200, 100],
      "id": "insert-individual"
    },
    {
      "parameters": {
        "functionCode": "// Préparer les groupes parallèles\nconst groups = items[0].json.parallelGroups || [];\n\nconst results = [];\n\nfor (const group of groups) {\n  // D'abord créer l'entrée pour parallel_groups\n  results.push({\n    json: {\n      type: 'group',\n      subject: group.subject,\n      grade: group.grade,\n      teachers: group.teachers.join(', '),\n      class_lists: group.details.map(d => d.class_list).join(' | ')\n    }\n  });\n  \n  // Ensuite créer les détails pour chaque professeur\n  for (const detail of group.details) {\n    results.push({\n      json: {\n        type: 'detail',\n        teacher_name: detail.teacher_name,\n        subject: detail.subject,\n        grade: detail.grade,\n        hours_per_teacher: detail.hours,\n        classes_covered: detail.class_list,\n        group_key: `${group.subject}_${group.grade}`\n      }\n    });\n  }\n}\n\nreturn results;"
      },
      "name": "Format Parallel Groups",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [1000, 300],
      "id": "format-parallel"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.type }}",
              "operation": "equals",
              "value2": "group"
            }
          ]
        }
      },
      "name": "Is Group?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [1200, 300],
      "id": "check-type"
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "parallel_groups",
        "columns": {
          "mappingMode": "defineBelow",
          "value": {
            "subject": "={{ $json.subject }}",
            "grade": "={{ $json.grade }}",
            "teachers": "={{ $json.teachers }}",
            "class_lists": "={{ $json.class_lists }}"
          }
        }
      },
      "name": "Insert Parallel Groups",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [1400, 250],
      "id": "insert-groups"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "-- Insérer les détails des cours parallèles\nWITH group_mapping AS (\n  SELECT \n    group_id,\n    subject,\n    grade\n  FROM parallel_groups\n)\nINSERT INTO parallel_teaching_details (\n  group_id,\n  teacher_name,\n  subject,\n  grade,\n  hours_per_teacher,\n  classes_covered\n)\nSELECT \n  gm.group_id,\n  '{{ $json.teacher_name }}',\n  '{{ $json.subject }}',\n  '{{ $json.grade }}',\n  {{ $json.hours_per_teacher }},\n  '{{ $json.classes_covered }}'\nFROM group_mapping gm\nWHERE gm.subject = '{{ $json.subject }}'\n  AND gm.grade = '{{ $json.grade }}';"
      },
      "name": "Insert Parallel Details",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [1400, 350],
      "id": "insert-details"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "-- Créer les contraintes pour les groupes parallèles\nINSERT INTO constraints (\n  constraint_type,\n  priority,\n  entity_type,\n  entity_name,\n  constraint_data\n)\nSELECT \n  'parallel_teaching',\n  1,\n  'group',\n  'parallel_group_' || pg.group_id,\n  jsonb_build_object(\n    'group_id', pg.group_id,\n    'subject', pg.subject,\n    'grade', pg.grade,\n    'teachers', string_to_array(pg.teachers, ', '),\n    'hours', MAX(ptd.hours_per_teacher),\n    'simultaneous', true,\n    'description', 'Cours parallèle: ' || pg.teachers || ' enseignent ' || pg.subject || ' niveau ' || pg.grade\n  )\nFROM parallel_groups pg\nJOIN parallel_teaching_details ptd ON pg.group_id = ptd.group_id\nGROUP BY pg.group_id, pg.subject, pg.grade, pg.teachers;"
      },
      "name": "Create Parallel Constraints",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [1600, 300],
      "id": "create-constraints"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "-- Rapport final\nSELECT \n  'Rapport d''import' as title,\n  (\n    SELECT jsonb_build_object(\n      'individual_loads', COUNT(*),\n      'parallel_groups', (SELECT COUNT(*) FROM parallel_groups),\n      'parallel_details', (SELECT COUNT(*) FROM parallel_teaching_details),\n      'constraints_created', (SELECT COUNT(*) FROM constraints WHERE constraint_type = 'parallel_teaching')\n    )\n    FROM teacher_load\n    WHERE is_parallel = FALSE\n  ) as stats;"
      },
      "name": "Final Report",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [1800, 300],
      "id": "final-report"
    }
  ],
  "connections": {
    "Analyze Parallel": {
      "main": [[
        { "node": "Clean Tables", "type": "main", "index": 0 }
      ]]
    },
    "Clean Tables": {
      "main": [[
        { "node": "Format Individual Loads", "type": "main", "index": 0 },
        { "node": "Format Parallel Groups", "type": "main", "index": 0 }
      ]]
    },
    "Format Individual Loads": {
      "main": [[
        { "node": "Insert Individual Loads", "type": "main", "index": 0 }
      ]]
    },
    "Format Parallel Groups": {
      "main": [[
        { "node": "Is Group?", "type": "main", "index": 0 }
      ]]
    },
    "Is Group?": {
      "main": [
        [{ "node": "Insert Parallel Groups", "type": "main", "index": 0 }],
        [{ "node": "Insert Parallel Details", "type": "main", "index": 0 }]
      ]
    },
    "Insert Individual Loads": {
      "main": [[
        { "node": "Create Parallel Constraints", "type": "main", "index": 0 }
      ]]
    },
    "Insert Parallel Groups": {
      "main": [[
        { "node": "Create Parallel Constraints", "type": "main", "index": 0 }
      ]]
    },
    "Insert Parallel Details": {
      "main": [[
        { "node": "Create Parallel Constraints", "type": "main", "index": 0 }
      ]]
    },
    "Create Parallel Constraints": {
      "main": [[
        { "node": "Final Report", "type": "main", "index": 0 }
      ]]
    }
  }
}