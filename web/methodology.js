(() => {
  "use strict";

  const API_BASE = (document.body.dataset.apiBase || "/api/v1").replace(/\/$/, "");
  const els = {};

  function cacheElements() {
    [
      "method-status", "model-version", "defuzzification", "model-loaded-at",
      "variables-content", "outputs-content", "rules-content",
      "validation-notes", "sources-content", "ulap-method-status"
    ].forEach((id) => {
      els[id] = document.getElementById(id);
    });
  }

  function escapeHtml(value) {
    return String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");
  }

  function firstDefined(...values) {
    return values.find((value) => value !== undefined && value !== null);
  }

  function textValue(value, fallback = "Not reported") {
    if (value === undefined || value === null || value === "") return fallback;
    return String(value);
  }

  function titleCase(value) {
    return textValue(value)
      .replaceAll("_", " ")
      .replaceAll("-", " ")
      .replace(/\b\w/g, (letter) => letter.toUpperCase());
  }

  function unwrap(value) {
    if (value && typeof value === "object" && "data" in value) return value.data;
    return value;
  }

  function objectToItems(value) {
    if (Array.isArray(value)) return value;
    if (!value || typeof value !== "object") return [];
    return Object.entries(value).map(([key, item]) =>
      item && typeof item === "object" ? { name: key, ...item } : { name: key, value: item }
    );
  }

  function asArray(payload) {
    const value = unwrap(payload);
    if (Array.isArray(value)) return value;
    if (!value || typeof value !== "object") return [];
    for (const key of ["items", "results", "sources", "data_sources", "datasets", "records"]) {
      if (Array.isArray(value[key])) return value[key];
    }
    return [];
  }

  function formatDate(value) {
    if (!value) return "Date not reported";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric"
    }).format(date);
  }

  function formatDateTime(value) {
    if (!value) return "Time not reported";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return String(value);
    return new Intl.DateTimeFormat(undefined, {
      year: "numeric",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
      timeZoneName: "short"
    }).format(date);
  }

  function normalizeStatus(value, fallback = "pending_verification") {
    const status = textValue(value, fallback).trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
    if (["healthy", "ready", "operational", "verified", "available", "official"].includes(status)) return "available";
    if (["verified_with_changed_metadata", "metadata_changed", "schema_changed", "missing_classification_field"].includes(status)) return "changed_schema";
    if (["auth_required", "unauthorized", "forbidden"].includes(status)) return "authentication_required";
    if (["error", "failed", "offline", "inaccessible"].includes(status)) return "service_error";
    if (["not_configured", "missing_endpoint"].includes(status)) return "unavailable";
    return status || fallback;
  }

  function statusKind(status) {
    const value = normalizeStatus(status);
    if (value === "available") return "success";
    if (["pending_verification", "changed_schema", "authentication_required"].includes(value)) return "warning";
    if (["unavailable", "outside_coverage", "no_intersection"].includes(value)) return "neutral";
    return "danger";
  }

  function safeSourceUrl(value) {
    if (!value) return null;
    try {
      const url = new URL(String(value), window.location.origin);
      if (!["http:", "https:"].includes(url.protocol)) return null;
      ["token", "access_token", "key", "api_key"].forEach((name) => url.searchParams.delete(name));
      return url.href;
    } catch {
      return null;
    }
  }

  function normalizeServiceCollection(payload) {
    const value = unwrap(payload);
    const items = asArray(value);
    if (items.length) return items;
    const root = firstDefined(value?.services, value?.serviceRegistry, value?.service_registry);
    if (!root || typeof root !== "object") return [];
    const flattened = [];
    const visit = (node, path = []) => {
      if (Array.isArray(node)) {
        node.forEach((item, index) => visit(item, [...path, String(index)]));
        return;
      }
      if (!node || typeof node !== "object") return;
      const looksLikeService = [
        "key", "layerUrl", "layer_url", "sourceUrl", "source_url",
        "layerId", "layer_id", "classificationField", "classification_field",
        "runtime_validation", "verification"
      ].some((key) => node[key] !== undefined);
      if (looksLikeService) {
        flattened.push({ hazard: firstDefined(node.hazard, node.hazard_type, path.at(-1)), ...node });
        return;
      }
      Object.entries(node).forEach(([key, child]) => {
        if (child && typeof child === "object") visit(child, [...path, key]);
      });
    };
    visit(root);
    return flattened;
  }

  function serviceKey(service) {
    return textValue(firstDefined(
      service.key,
      service.service,
      service.hazard_type,
      service.hazard,
      service.slug
    ), "").trim().toLowerCase().replace(/[^a-z0-9]+/g, "_");
  }

  function serviceStatus(service) {
    return normalizeStatus(firstDefined(
      service.runtime_validation?.status,
      service.runtimeValidation?.status,
      service.verification?.status,
      service.verificationStatus,
      service.verification_status,
      service.healthStatus,
      service.health_status,
      service.status
    ), service.configured === false ? "unavailable" : "pending_verification");
  }

  function mergeServiceValidations(services, statusPayload) {
    const value = unwrap(statusPayload) || {};
    const validations = asArray(firstDefined(value.services, value.service_results, value.results));
    if (!validations.length) return services;
    const byKey = new Map(validations.map((validation) => [
      serviceKey(validation),
      validation
    ]).filter(([key]) => key));
    return services.map((service) => {
      const validation = byKey.get(serviceKey(service));
      if (!validation) return service;
      return {
        ...service,
        runtime_validation: {
          ...(service.runtime_validation || {}),
          ...validation
        }
      };
    });
  }

  function serviceSources(payload) {
    return normalizeServiceCollection(payload).map((service) => ({
      ...service,
      name: firstDefined(service.displayName, service.display_name, service.layerName, service.layer_name, service.name, service.key, service.service, service.hazard),
      subject: firstDefined(service.hazard, service.hazard_type, service.key, service.dataset, service.type),
      provider: firstDefined(service.agency, service.provider, service.organization),
      data_status: serviceStatus(service),
      source_url: firstDefined(service.layerUrl, service.layer_url, service.sourceUrl, service.source_url, service.url),
      source_date: firstDefined(service.dataDate, service.data_date),
      retrieved_at: firstDefined(
        service.runtime_validation?.checked_at,
        service.runtimeValidation?.checkedAt,
        service.retrievedAt,
        service.retrieved_at,
        service.checkedAt,
        service.checked_at
      ),
      layer_id: firstDefined(service.layerId, service.layer_id),
      classification_field: firstDefined(service.classificationField, service.classification_field),
      spatial_reference: firstDefined(service.spatialReference?.wkid, service.spatialReference, service.spatial_reference?.wkid, service.spatial_reference),
      quality_notice: firstDefined(service.message, service.notes, service.warnings),
      attribution: firstDefined(service.attribution, service.copyrightText, service.copyright_text)
    }));
  }

  function setStatus(kind, message) {
    els["method-status"].className = `system-status is-${kind}`;
    els["method-status"].querySelector("span:last-child").textContent = message;
  }

  async function apiFetch(path) {
    const controller = new AbortController();
    const timeout = window.setTimeout(() => controller.abort(), 15000);
    try {
      const response = await fetch(`${API_BASE}${path}`, {
        headers: { Accept: "application/json" },
        signal: controller.signal
      });
      if (!response.ok) throw new Error(`Request failed (${response.status})`);
      return response.json();
    } finally {
      window.clearTimeout(timeout);
    }
  }

  function emptyBlock(subject) {
    return `<div class="empty-api-block"><strong>${escapeHtml(subject)} unavailable.</strong><br>The interface will not invent configuration values. Consult the version-controlled model and deployment records before interpreting assessments.</div>`;
  }

  function membershipSummary(membership) {
    const type = textValue(firstDefined(
      membership.function_type,
      membership.type,
      membership.membership_function_type,
      membership.shape
    ));
    const parameters = firstDefined(
      membership.parameters,
      membership.params,
      membership.function_parameters
    );
    let parameterText;
    if (Array.isArray(parameters)) {
      parameterText = parameters.join(", ");
    } else if (parameters && typeof parameters === "object") {
      parameterText = Object.entries(parameters).map(([key, value]) => `${key}=${value}`).join(", ");
    } else {
      const known = ["a", "b", "c", "d", "mean", "sigma", "min", "max"]
        .filter((key) => membership[key] !== undefined)
        .map((key) => `${key}=${membership[key]}`);
      parameterText = known.join(", ") || textValue(parameters, "Parameters not reported");
    }
    return `<span class="parameter-list"><code>${escapeHtml(type)}</code><code>${escapeHtml(parameterText)}</code></span>`;
  }

  function membershipsForVariable(variable, model) {
    const embedded = objectToItems(firstDefined(
      variable.membership_functions,
      variable.memberships,
      variable.linguistic_categories
    ));
    if (embedded.length) return embedded;
    const variableId = firstDefined(variable.id, variable.variable_id);
    const variableName = firstDefined(variable.name, variable.code, variable.key);
    return objectToItems(firstDefined(model.membership_functions, model.memberships)).filter((membership) => {
      const memberVariable = firstDefined(
        membership.variable_id,
        membership.fuzzy_variable_id,
        membership.variable_name,
        membership.variable?.name
      );
      return String(memberVariable) === String(variableId) || String(memberVariable) === String(variableName);
    });
  }

  function renderVariables(model) {
    const variables = objectToItems(firstDefined(
      model.input_variables,
      model.variables,
      model.fuzzy_variables,
      model.inputs
    )).filter((variable) => {
      const role = textValue(firstDefined(variable.role, variable.kind, variable.variable_type), "input");
      return !/output/i.test(role);
    });

    if (!variables.length) {
      els["variables-content"].innerHTML = emptyBlock("Input-variable configuration");
      return;
    }
    els["variables-content"].innerHTML = `
      <table class="method-table">
        <caption class="visually-hidden">Fuzzy input variables and membership functions</caption>
        <thead><tr><th>Input variable</th><th>Domain / normalization</th><th>Linguistic category and function</th></tr></thead>
        <tbody>${variables.map((variable) => {
          const memberships = membershipsForVariable(variable, model);
          const name = textValue(firstDefined(variable.display_name, variable.name, variable.label, variable.code));
          const domain = firstDefined(
            variable.domain,
            variable.range,
            variable.normalization,
            variable.normalization_notes
          );
          const domainText = Array.isArray(domain)
            ? domain.join("–")
            : domain && typeof domain === "object"
              ? Object.entries(domain).map(([key, value]) => `${key}: ${value}`).join(", ")
              : textValue(domain);
          return `<tr>
            <td><strong>${escapeHtml(name)}</strong>${variable.description ? `<br><small>${escapeHtml(variable.description)}</small>` : ""}</td>
            <td>${escapeHtml(domainText)}</td>
            <td>${memberships.length
              ? memberships.map((membership) => {
                const label = firstDefined(
                  membership.linguistic_category,
                  membership.category,
                  membership.label,
                  membership.name,
                  membership.term
                );
                return `<div><strong>${escapeHtml(titleCase(label))}</strong> ${membershipSummary(membership)}</div>`;
              }).join("")
              : "Membership functions not reported"}</td>
          </tr>`;
        }).join("")}</tbody>
      </table>`;
  }

  function renderOutputs(model) {
    let outputs = objectToItems(firstDefined(
      model.output_categories,
      model.category_thresholds,
      model.outputs,
      model.output_membership_functions
    ));
    if (outputs.length === 1 && objectToItems(outputs[0].categories).length) {
      outputs = objectToItems(outputs[0].categories);
    }
    if (!outputs.length) {
      els["outputs-content"].innerHTML = emptyBlock("Output-category thresholds");
      return;
    }
    els["outputs-content"].innerHTML = `
      <table class="method-table">
        <caption class="visually-hidden">Fuzzy output categories and thresholds</caption>
        <thead><tr><th>Category</th><th>Score threshold or range</th><th>Output function</th></tr></thead>
        <tbody>${outputs.map((output) => {
          const name = firstDefined(output.display_name, output.category, output.label, output.name);
          const min = firstDefined(output.minimum, output.min, output.lower_bound, output.from);
          const max = firstDefined(output.maximum, output.max, output.upper_bound, output.to);
          const range = firstDefined(
            output.threshold,
            output.range,
            min !== undefined || max !== undefined ? `${textValue(min, "…")}–${textValue(max, "…")}` : null
          );
          const hasFunction = firstDefined(output.function_type, output.type, output.membership_function_type);
          return `<tr>
            <td><strong>${escapeHtml(titleCase(name))}</strong></td>
            <td>${escapeHtml(textValue(range))}</td>
            <td>${hasFunction ? membershipSummary(output) : "Function not reported"}</td>
          </tr>`;
        }).join("")}</tbody>
      </table>`;
  }

  function renderRules(model) {
    const rules = objectToItems(firstDefined(model.rules, model.fuzzy_rules, model.rule_base));
    if (!rules.length) {
      els["rules-content"].innerHTML = emptyBlock("Fuzzy rule statements");
      return;
    }
    els["rules-content"].innerHTML = `<div class="rule-cards">${rules.map((rule, index) => {
      const id = firstDefined(rule.code, rule.rule_code, rule.id, `R${index + 1}`);
      const statement = firstDefined(
        rule.statement,
        rule.rule_statement,
        rule.description,
        rule.expression
      );
      const weight = firstDefined(rule.weight, rule.rule_weight, 1);
      return `<article class="rule-card">
        <span class="rule-id">${escapeHtml(id)}</span>
        <p>${escapeHtml(textValue(statement, "Rule statement not reported"))}</p>
        <span class="rule-weight">Weight ${escapeHtml(weight)}</span>
      </article>`;
    }).join("")}</div>`;
  }

  function renderValidation(model) {
    const notes = firstDefined(model.validation_notes, model.validation_note, model.notes);
    const items = Array.isArray(notes) ? notes : notes ? [notes] : [];
    const validationStatus = firstDefined(model.validation_status, model.status);
    const validated = /^(validated|approved)$/i.test(textValue(validationStatus, ""));
    els["validation-notes"].innerHTML = `
      <strong>${validated ? "Domain validation recorded" : "Domain validation required"}</strong>
      <p>${items.length
        ? items.map((item) => escapeHtml(typeof item === "string" ? item : textValue(item.message || item.note))).join(" ")
        : "Configured transformations, thresholds, and rules must be reviewed and validated by qualified domain experts before operational planning use."}</p>`;
  }

  function sourceStatus(source) {
    if (source.is_official === true) return "Official";
    return titleCase(normalizeStatus(firstDefined(source.data_status, source.status, source.provenance_status)));
  }

  function renderSources(payload) {
    const seen = new Set();
    const sources = asArray(payload).filter((source) => {
      const status = textValue(firstDefined(source.data_status, source.status, source.provenance_status), "");
      const accepted = source.is_demo !== true
        && source.demonstration !== true
        && !/demo|synthetic|placeholder|mock/i.test(status);
      if (!accepted) return false;
      const key = textValue(firstDefined(
        source.layerUrl,
        source.layer_url,
        source.sourceUrl,
        source.source_url,
        source.name,
        source.service
      ), JSON.stringify(source));
      if (seen.has(key)) return false;
      seen.add(key);
      return true;
    });
    if (!sources.length) {
      els["sources-content"].innerHTML = emptyBlock("Data-source register");
      return;
    }
    els["sources-content"].innerHTML = `
      <table class="method-table">
        <caption class="visually-hidden">Data source register</caption>
        <thead><tr><th>Dataset / source</th><th>Provider, layer &amp; time</th><th>Status</th><th>Quality, attribution &amp; URL</th></tr></thead>
        <tbody>${sources.map((source) => {
          const name = firstDefined(source.name, source.title, source.dataset_name, source.subject);
          const provider = firstDefined(source.provider, source.agency, source.organization);
          const date = firstDefined(source.reference_date, source.source_date, source.updated_at, source.date);
          const status = sourceStatus(source);
          const layerId = firstDefined(source.layer_id, source.layerId);
          const retrievedAt = firstDefined(source.retrieved_at, source.retrievedAt, source.checked_at, source.checkedAt);
          const classificationField = firstDefined(source.classification_field, source.classificationField);
          const spatialReference = firstDefined(source.spatial_reference, source.spatialReference);
          const sourceUrl = safeSourceUrl(firstDefined(source.source_url, source.sourceUrl, source.layer_url, source.layerUrl, source.url));
          const notes = firstDefined(
            source.quality_notice,
            source.quality_notes,
            source.data_quality,
            source.limitations,
            source.availability_notes,
            source.description
          );
          const renderedNotes = Array.isArray(notes)
            ? notes.join(" ")
            : notes && typeof notes === "object"
              ? [
                notes.summary,
                ...(Array.isArray(notes.limitations) ? notes.limitations : [])
              ].filter(Boolean).join(" ")
              : textValue(notes, "No quality note reported");
          return `<tr>
            <td><strong>${escapeHtml(textValue(name, "Unnamed source"))}</strong></td>
            <td>${escapeHtml(textValue(firstDefined(provider, source.source_name)))}<br><small>${escapeHtml([
              layerId !== undefined && layerId !== null ? `Layer ${layerId}` : null,
              classificationField ? `Field ${classificationField}` : null,
              spatialReference ? `SR ${typeof spatialReference === "object" ? JSON.stringify(spatialReference) : spatialReference}` : null,
              `Data date ${formatDate(date)}`,
              retrievedAt ? `Retrieved ${formatDateTime(retrievedAt)}` : null
            ].filter(Boolean).join(" · "))}</small></td>
            <td><span class="badge ${status === "Official" ? "success" : statusKind(status)}">${escapeHtml(status)}</span></td>
            <td>${escapeHtml(renderedNotes)}${source.attribution ? `<br><small>${escapeHtml(source.attribution)}</small>` : ""}${sourceUrl ? `<br><a href="${escapeHtml(sourceUrl)}" target="_blank" rel="noopener noreferrer">Official layer metadata</a>` : ""}</td>
          </tr>`;
        }).join("")}</tbody>
      </table>`;
  }

  function renderUlapStatus(payload, services) {
    const value = unwrap(payload) || {};
    const status = normalizeStatus(firstDefined(value.overallStatus, value.overall_status, value.status, value.health), services.length ? "available" : "unavailable");
    const checkedAt = firstDefined(value.checkedAt, value.checked_at, value.retrievedAt, value.retrieved_at);
    const unavailable = services.filter((service) => serviceStatus(service) !== "available");
    const serviceHazards = services.map((service) => [
      service.hazard,
      service.hazard_type,
      service.key,
      service.dataset,
      service.type,
      service.name,
      service.service,
      service.layerName,
      service.layer_name
    ].filter((item) => item !== undefined && item !== null).join(" ").toLowerCase().replace(/[^a-z0-9]+/g, "_"));
    const missingRequired = [
      ["flood", "Flood"],
      ["liqu", "Liquefaction"],
      ["shak", "Ground shaking"]
    ].filter(([needle]) => !serviceHazards.some((value) => value.includes(needle))).map(([, label]) => label);
    els["ulap-method-status"].className = `callout ${status === "available" && !unavailable.length ? "important" : "caution"}`;
    els["ulap-method-status"].innerHTML = `
      <strong>ULAP service health: ${escapeHtml(titleCase(status))}</strong>
      <p>${escapeHtml(textValue(firstDefined(value.message, value.summary), checkedAt ? `Last checked ${formatDateTime(checkedAt)}.` : "Validation time not reported."))}
      ${unavailable.length ? ` ${unavailable.length} registered service${unavailable.length === 1 ? " is" : "s are"} not fully available.` : ""}
      ${missingRequired.length ? ` No verified endpoint was returned for ${escapeHtml(missingRequired.join(", "))}.` : ""}
      ${unavailable.length || missingRequired.length ? " Required missing hazards block a complete score." : ""}</p>`;
  }

  function renderModel(payload) {
    const value = unwrap(payload) || {};
    const model = firstDefined(value.model, value.fuzzy_model, value.methodology, value) || {};
    els["model-version"].textContent = textValue(firstDefined(model.version, model.model_version));
    els.defuzzification.textContent = titleCase(firstDefined(
      model.defuzzification_method,
      model.defuzzification,
      model.inference?.defuzzification_method,
      model.inference?.defuzzification
    ));
    els["model-loaded-at"].textContent = formatDate(firstDefined(
      model.updated_at,
      model.effective_date,
      model.created_at
    ));
    renderVariables(model);
    renderOutputs(model);
    renderRules(model);
    renderValidation(model);
  }

  async function start() {
    cacheElements();
    const ulapRegistry = async () => {
      const status = await apiFetch("/ulap/status");
      const services = await apiFetch("/ulap/services");
      return { status, services };
    };
    const [methodResult, ulapResult, sourcesResult] = await Promise.allSettled([
      apiFetch("/methodology"),
      ulapRegistry(),
      apiFetch("/data-sources")
    ]);

    if (methodResult.status === "fulfilled") {
      renderModel(methodResult.value);
    } else {
      renderModel({});
    }
    const services = ulapResult.status === "fulfilled"
      ? mergeServiceValidations(
        normalizeServiceCollection(ulapResult.value.services),
        ulapResult.value.status
      )
      : [];
    const liveSources = ulapResult.status === "fulfilled"
      ? serviceSources(services)
      : [];
    const catalogueSources = sourcesResult.status === "fulfilled"
      ? asArray(sourcesResult.value)
      : [];
    renderSources([...liveSources, ...catalogueSources]);
    renderUlapStatus(
      ulapResult.status === "fulfilled" ? ulapResult.value.status : { status: "service_error", message: "ULAP health status could not be retrieved." },
      services
    );

    if (methodResult.status === "fulfilled" && ulapResult.status === "fulfilled") {
      setStatus("online", "Model and ULAP records loaded");
    } else if (methodResult.status === "fulfilled" || ulapResult.status === "fulfilled") {
      setStatus("online", "Partial live records loaded");
    } else {
      setStatus("offline", "Model service unavailable");
    }
  }

  start().catch(() => {
    setStatus("offline", "Model service unavailable");
    renderModel({});
    renderSources([]);
    renderUlapStatus({ status: "service_error" }, []);
  });
})();
