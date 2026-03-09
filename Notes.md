These notes summarize a CRUD matrix and a small set of confirmed endpoint examples based on the BQE CORE API Explorer pages cited below.

> Note: The spreadsheet referenced in an earlier draft is not stored in this repo, so this Markdown file is the canonical version here.

## How to read this

- **CRUD** is expressed as:
  - **C** = Create (typically `POST`)
  - **R** = Read (typically `GET`)
  - **U** = Update (typically `PUT` and sometimes `PATCH`)
  - **D** = Delete (typically `DELETE`)
- CORE's docs explicitly describe standard REST method usage. ([BQE Core API Explorer][1])
- Some resources also expose async batch endpoints that return a Job, such as `/project/batch`, `/document/batch`, `/crm/prospect/batch`, `/hr/employeebenefit/batch`, and `/hr/employeebenefitusage/batch`. ([BQE Core API Explorer][2]) ([BQE Core API Explorer][5]) ([BQE Core API Explorer][6]) ([BQE Core API Explorer][11])

## Read-only or limited resources

These are the clearest documented cases where the API is read-only or utility-oriented:

- **Company**: read-only company endpoints. ([BQE Core API Explorer][3])
- **ResourceSchedule**: read-only, with an additional `/resourceschedule/week` endpoint. ([BQE Core API Explorer][4])
- **Health**: utility read endpoint at `/health`. ([BQE Core API Explorer][9])
- **Version**: utility read endpoint at `/version`. ([BQE Core API Explorer][10])

`EmployeeBenefit` and `EmployeeBenefitUsage` are not read-only in the API Explorer metadata. Both are described as supporting retrieve/create/update/delete operations. ([BQE Core API Explorer][5]) ([BQE Core API Explorer][6])

## Resource matrix

> Note: The table mixes directly confirmed paths with a few naming-pattern inferences. Confirm each resource page before implementation when the exact path shape matters.

| Module  | Resource             | Base endpoints                                            | CRUD |
| :------ | :------------------- | :-------------------------------------------------------- | :--- |
| CRM     | LeadSource           | /crm/lists/leadsource                                     | CRUD |
| CRM     | Prospect             | /crm/prospect, /crm/prospect/batch                        | CRUD |
| CRM     | Region               | /crm/lists/region                                         | CRUD |
| CRM     | Score                | /crm/lists/score                                          | CRUD |
| General | Activity             | /activity                                                 | CRUD |
| General | Allocation           | /allocation                                               | CRUD |
| General | Bill                 | /bill                                                     | CRUD |
| General | Check                | /check                                                    | CRUD |
| General | Client               | /client                                                   | CRUD |
| General | Company              | /company                                                  | R    |
| General | Document             | /document, /document/batch, /document/uri                 | CRUD |
| General | Employee             | /employee                                                 | CRUD |
| General | FeeSchedule          | /feeschedule                                              | CRUD |
| General | Invoice              | /invoice                                                  | CRUD |
| General | Payment              | /payment                                                  | CRUD |
| General | Project              | /project, /project/batch                                  | CRUD |
| General | ResourceSchedule     | /resourceschedule, /resourceschedule/week                 | R    |
| General | TimeEntry            | /timeentry                                                | CRUD |
| HR      | Benefit              | /hr/benefit                                               | CRUD |
| HR      | EmployeeBenefit      | /hr/employeebenefit, /hr/employeebenefit/batch            | CRUD |
| HR      | EmployeeBenefitUsage | /hr/employeebenefitusage, /hr/employeebenefitusage/batch  | CRUD |
| HR      | Journal              | /hr/journal                                               | CRUD |
| HR      | JournalType          | /hr/journaltype                                           | CRUD |
| HR      | Question             | /hr/question                                              | CRUD |
| HR      | Review               | /hr/review                                                | CRUD |
| HR      | ReviewTemplate       | /hr/reviewtemplate                                        | CRUD |
| System  | Health               | /health                                                   | R    |
| System  | Version              | /version                                                  | R    |

Representative sources: Project with batch and subresources ([BQE Core API Explorer][2]); Document with batch and `uri` access ([BQE Core API Explorer][8]); LeadSource under `/crm/lists` ([BQE Core API Explorer][7]); Prospect including batch operations ([BQE Core API Explorer][11]); Company read-only behavior ([BQE Core API Explorer][3]); ResourceSchedule read-only behavior ([BQE Core API Explorer][4]); EmployeeBenefit and EmployeeBenefitUsage CRUD metadata ([BQE Core API Explorer][5]) ([BQE Core API Explorer][6]); utility endpoints `/health` and `/version` ([BQE Core API Explorer][9]) ([BQE Core API Explorer][10]).

## Endpoint examples (confirmed paths + methods)

These are directly confirmed from the API Explorer pages.

### Project (General)

- `GET /project` (list) ([BQE Core API Explorer][2])
- `POST /project/batch` (batch save; returns Job) ([BQE Core API Explorer][2])
- `PATCH /project/{id}` (partial modification) ([BQE Core API Explorer][2])
- `GET /project/{id}/resources` (list assigned resources) ([BQE Core API Explorer][2])
- `GET /project/{id}/activities` (list assigned activities) ([BQE Core API Explorer][2])

Project is also documented as supporting create, update, and delete operations overall. ([BQE Core API Explorer][2])

### Document (General)

- `GET /document` (list) ([BQE Core API Explorer][8])
- `POST /document/batch` (batch create via hyperlinks; returns Job) ([BQE Core API Explorer][8])
- `GET /document/uri/{id}` (return document link as a string) ([BQE Core API Explorer][8])

The Document API is also documented as supporting create, update, and delete operations overall. ([BQE Core API Explorer][8])

### Lead Source (CRM lists)

- `GET /crm/lists/leadsource` (list) ([BQE Core API Explorer][7])
- `GET /crm/lists/leadsource/{id}` (retrieve) ([BQE Core API Explorer][7])
- `POST /crm/lists/leadsource` (create) ([BQE Core API Explorer][7])
- `PUT /crm/lists/leadsource/{id}` (update) ([BQE Core API Explorer][7])
- `DELETE /crm/lists/leadsource/{id}` (delete) ([BQE Core API Explorer][7])

### Utility endpoints

- `GET /health` ([BQE Core API Explorer][9])
- `GET /version` ([BQE Core API Explorer][10])

## Notes on confidence

- The examples section contains only endpoints confirmed directly from the cited API pages.
- The matrix is intended as a planning aid, not a substitute for checking the resource-specific page before implementation.
- Where the docs expose batch endpoints, they generally return a Job and should be treated as async operations.

[1]: https://api-explorer.bqecore.com/docs/api-methods "BQE Core API methods"
[2]: https://api-explorer.bqecore.com/docs/api/apis/project "Project API"
[3]: https://api-explorer.bqecore.com/docs/api/apis/company "Company API"
[4]: https://api-explorer.bqecore.com/docs/api/apis/resourceschedule "ResourceSchedule API"
[5]: https://api-explorer.bqecore.com/docs/api/apis/hr-employeebenefit "EmployeeBenefit API"
[6]: https://api-explorer.bqecore.com/docs/api/apis/hr-employeebenefitusage "EmployeeBenefitUsage API"
[7]: https://api-explorer.bqecore.com/docs/api/apis/crm-leadsource "LeadSource API"
[8]: https://api-explorer.bqecore.com/docs/api/apis/document "Document API"
[9]: https://api-explorer.bqecore.com/docs/api/apis/health "Health API"
[10]: https://api-explorer.bqecore.com/docs/api/apis/version "Version API"
[11]: https://api-explorer.bqecore.com/docs/api/apis/prospect "Prospect API"
