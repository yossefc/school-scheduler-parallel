{
  "name": "Import Excel Emploi du Temps",
  "nodes": [
    {
      "parameters": {
        "triggerOn": "folder",
        "path": "/exports",
        "events": ["add"],
        "options": {
          "ignoreInitial": false
        }
      },
      "name": "Watch Folder",
      "type": "n8n-nodes-base.localFileTrigger",
      "typeVersion": 1,
      "position": [-1200, 300],
      "id": "trigger-1"
    },
    {
      "parameters": {
        "conditions": {
          "string": [
            {
              "value1": "={{ $json.path.toLowerCase() }}",
              "operation": "endsWith",
              "value2": ".xlsx"
            }
          ]
        }
      },
      "name": "Filter Excel Files",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [-1000, 300],
      "id": "filter-1"
    },
    {
      "parameters": {
        "filePath": "={{ $json.path }}"
      },
      "name": "Read Excel File",
      "type": "n8n-nodes-base.readBinaryFile",
      "typeVersion": 1,
      "position": [-800, 200],
      "id": "read-1"
    },
    {
      "parameters": {
        "requestMethod": "POST",
        "url": "http://solver:8000/parse",
        "jsonParameters": true,
        "options": {
          "bodyContentType": "multipart-form-data"
        },
        "sendBinaryData": true
      },
      "name": "Parse Excel",
      "type": "n8n-nodes-base.httpRequest",
      "typeVersion": 1,
      "position": [-600, 200],
      "id": "parse-1"
    },
    {
      "parameters": {
        "functionCode": "// Extraction et validation des données\nconst data = items[0].json;\n\n// Log pour debug\nconsole.log('Données reçues:', Object.keys(data));\n\n// Préparation des données avec validation\nconst result = {\n  metadata: {\n    filename: items[0].binary?.data?.fileName || 'unknown',\n    importedAt: new Date().toISOString(),\n    rowCounts: {\n      teachers: (data.teachers || []).length,\n      teacherSubjects: (data.teacher_subjects || []).length,\n      parallelGroups: (data.parallel_groups || []).length,\n      constraints: (data.constraints || []).length\n    }\n  },\n  data: {\n    teachers: data.teachers || [],\n    teacherSubjects: data.teacher_subjects || [],\n    parallelGroups: data.parallel_groups || [],\n    constraints: data.constraints || []\n  }\n};\n\nreturn [{ json: result }];"
      },
      "name": "Prepare Data",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [-400, 200],
      "id": "prepare-1"
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "BEGIN TRANSACTION;"
      },
      "name": "Start Transaction",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [-200, 200],
      "id": "transaction-start",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Préparer les enseignants pour insertion\nconst teachers = items[0].json.data.teachers.map(teacher => ({\n  json: {\n    teacher_name: teacher.teacher_name,\n    total_hours: Number(teacher.total_hours) || null,\n    work_days: teacher.work_days || null,\n    email: teacher.email || null,\n    phone: teacher.phone || null\n  }\n}));\n\nreturn teachers.length > 0 ? teachers : [{ json: { skip: true } }];"
      },
      "name": "Format Teachers",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [0, 0],
      "id": "format-teachers"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.skip }}",
              "operation": "notEqual",
              "value2": true
            }
          ]
        }
      },
      "name": "Has Teachers?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [200, 0],
      "id": "check-teachers"
    },
    {
      "parameters": {
        "operation": "upsert",
        "schema": "public",
        "table": "teachers",
        "columns": {
          "mappingMode": "defineBelow",
          "value": {
            "teacher_name": "={{ $json.teacher_name }}",
            "total_hours": "={{ $json.total_hours }}",
            "work_days": "={{ $json.work_days }}",
            "email": "={{ $json.email }}",
            "phone": "={{ $json.phone }}"
          }
        },
        "additionalFields": {
          "onConflictFields": "teacher_name"
        }
      },
      "name": "Upsert Teachers",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [400, -50],
      "id": "upsert-teachers",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Préparer les charges d'enseignement\nconst teacherSubjects = items[0].json.data.teacherSubjects.map(load => ({\n  json: {\n    teacher_name: load.teacher_name,\n    subject: load.subject,\n    grade: String(load.grade),\n    class_list: Array.isArray(load.class_list) ? load.class_list.join(',') : load.class_list,\n    hours: Number(load.hours) || 0,\n    work_days: load.work_days || null\n  }\n}));\n\nreturn teacherSubjects.length > 0 ? teacherSubjects : [{ json: { skip: true } }];"
      },
      "name": "Format Teacher Load",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [0, 200],
      "id": "format-load"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.skip }}",
              "operation": "notEqual",
              "value2": true
            }
          ]
        }
      },
      "name": "Has Load?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [200, 200],
      "id": "check-load"
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
            "work_days": "={{ $json.work_days }}"
          }
        }
      },
      "name": "Insert Teacher Load",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [400, 150],
      "id": "insert-load",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Préparer les groupes parallèles\nconst parallelGroups = items[0].json.data.parallelGroups.map(group => ({\n  json: {\n    subject: group.subject,\n    grade: String(group.grade),\n    teachers: Array.isArray(group.teachers) ? group.teachers.join(',') : group.teachers,\n    class_lists: Array.isArray(group.class_lists) ? group.class_lists.join(',') : group.class_lists\n  }\n}));\n\nreturn parallelGroups.length > 0 ? parallelGroups : [{ json: { skip: true } }];"
      },
      "name": "Format Parallel Groups",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [0, 400],
      "id": "format-parallel"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.skip }}",
              "operation": "notEqual",
              "value2": true
            }
          ]
        }
      },
      "name": "Has Parallels?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [200, 400],
      "id": "check-parallel"
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
      "position": [400, 350],
      "id": "insert-parallel",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "functionCode": "// Préparer les contraintes\nconst constraints = items[0].json.data.constraints.map(constraint => ({\n  json: {\n    type: constraint.type || 'custom',\n    weight: Number(constraint.weight) || 1,\n    details: JSON.stringify(constraint.details || {}),\n    source: 'excel_import',\n    created_at: new Date().toISOString()\n  }\n}));\n\nreturn constraints.length > 0 ? constraints : [{ json: { skip: true } }];"
      },
      "name": "Format Constraints",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [0, 600],
      "id": "format-constraints"
    },
    {
      "parameters": {
        "conditions": {
          "boolean": [
            {
              "value1": "={{ $json.skip }}",
              "operation": "notEqual",
              "value2": true
            }
          ]
        }
      },
      "name": "Has Constraints?",
      "type": "n8n-nodes-base.if",
      "typeVersion": 1,
      "position": [200, 600],
      "id": "check-constraints"
    },
    {
      "parameters": {
        "operation": "insert",
        "schema": "public",
        "table": "constraints",
        "columns": {
          "mappingMode": "defineBelow",
          "value": {
            "type": "={{ $json.type }}",
            "weight": "={{ $json.weight }}",
            "details": "={{ $json.details }}",
            "source": "={{ $json.source }}",
            "created_at": "={{ $json.created_at }}"
          }
        }
      },
      "name": "Insert Constraints",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [400, 550],
      "id": "insert-constraints",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "COMMIT;"
      },
      "name": "Commit Transaction",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [600, 300],
      "id": "transaction-commit",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {
        "operation": "executeQuery",
        "query": "ROLLBACK;"
      },
      "name": "Rollback on Error",
      "type": "n8n-nodes-base.postgres",
      "typeVersion": 2.5,
      "position": [400, 700],
      "id": "transaction-rollback",
      "credentials": {
        "postgres": {
          "id": "Uv6nxTakuIjU15U4",
          "name": "Postgres account"
        }
      }
    },
    {
      "parameters": {},
      "name": "Error Handler",
      "type": "n8n-nodes-base.errorTrigger",
      "typeVersion": 1,
      "position": [200, 700],
      "id": "error-handler"
    },
    {
      "parameters": {
        "functionCode": "return [{\n  json: {\n    status: 'success',\n    message: 'Import terminé avec succès',\n    counts: items[0].json.metadata.rowCounts,\n    timestamp: new Date().toISOString()\n  }\n}];"
      },
      "name": "Success Message",
      "type": "n8n-nodes-base.function",
      "typeVersion": 1,
      "position": [800, 300],
      "id": "success-msg"
    }
  ],
  "connections": {
    "Watch Folder": {
      "main": [[{ "node": "Filter Excel Files", "type": "main", "index": 0 }]]
    },
    "Filter Excel Files": {
      "main": [
        [{ "node": "Read Excel File", "type": "main", "index": 0 }],
        []
      ]
    },
    "Read Excel File": {
      "main": [[{ "node": "Parse Excel", "type": "main", "index": 0 }]]
    },
    "Parse Excel": {
      "main": [[{ "node": "Prepare Data", "type": "main", "index": 0 }]]
    },
    "Prepare Data": {
      "main": [[{ "node": "Start Transaction", "type": "main", "index": 0 }]]
    },
    "Start Transaction": {
      "main": [[
        { "node": "Format Teachers", "type": "main", "index": 0 },
        { "node": "Format Teacher Load", "type": "main", "index": 0 },
        { "node": "Format Parallel Groups", "type": "main", "index": 0 },
        { "node": "Format Constraints", "type": "main", "index": 0 }
      ]]
    },
    "Format Teachers": {
      "main": [[{ "node": "Has Teachers?", "type": "main", "index": 0 }]]
    },
    "Has Teachers?": {
      "main": [
        [{ "node": "Upsert Teachers", "type": "main", "index": 0 }],
        [{ "node": "Commit Transaction", "type": "main", "index": 0 }]
      ]
    },
    "Upsert Teachers": {
      "main": [[{ "node": "Commit Transaction", "type": "main", "index": 0 }]]
    },
    "Format Teacher Load": {
      "main": [[{ "node": "Has Load?", "type": "main", "index": 0 }]]
    },
    "Has Load?": {
      "main": [
        [{ "node": "Insert Teacher Load", "type": "main", "index": 0 }],
        [{ "node": "Commit Transaction", "type": "main", "index": 0 }]
      ]
    },
    "Insert Teacher Load": {
      "main": [[{ "node": "Commit Transaction", "type": "main", "index": 0 }]]
    },
    "Format Parallel Groups": {
      "main": [[{ "node": "Has Parallels?", "type": "main", "index": 0 }]]
    },
    "Has Parallels?": {
      "main": [
        [{ "node": "Insert Parallel Groups", "type": "main", "index": 0 }],
        [{ "node": "Commit Transaction", "type": "main", "index": 0 }]
      ]
    },
    "Insert Parallel Groups": {
      "main": [[{ "node": "Commit Transaction", "type": "main", "index": 0 }]]
    },
    "Format Constraints": {
      "main": [[{ "node": "Has Constraints?", "type": "main", "index": 0 }]]
    },
    "Has Constraints?": {
      "main": [
        [{ "node": "Insert Constraints", "type": "main", "index": 0 }],
        [{ "node": "Commit Transaction", "type": "main", "index": 0 }]
      ]
    },
    "Insert Constraints": {
      "main": [[{ "node": "Commit Transaction", "type": "main", "index": 0 }]]
    },
    "Commit Transaction": {
      "main": [[{ "node": "Success Message", "type": "main", "index": 0 }]]
    },
    "Error Handler": {
      "main": [[{ "node": "Rollback on Error", "type": "main", "index": 0 }]]
    }
  }
}