const METADATA_FIELDS = [
  ["company", "Şirket"],
  ["location", "Konum"],
  ["employment_type", "Çalışma türü"],
  ["work_arrangement", "Çalışma düzeni"],
  ["salary", "Ücret"],
  ["experience", "Deneyim"],
  ["education", "Eğitim"],
  ["application_url", "Başvuru bağlantısı"],
];

const PROFILE_LEVELS = {
  beginner: "Başlangıç",
  intermediate: "Orta",
  advanced: "İleri",
  expert: "Uzman",
};

const SKILL_CATEGORIES = {
  language: "Programlama dili",
  framework: "Framework",
  database: "Veritabanı",
  tool: "Araç",
  runtime: "Çalışma ortamı",
  library: "Kütüphane",
  platform: "Platform",
  cloud: "Bulut",
  concept: "Kavram",
};

const SECTION_MATCHES = [
  ["required", "Zorunlu beceriler"],
  ["preferred", "Tercih edilen beceriler"],
  ["unspecified", "Bölümü belirtilmeyen beceriler"],
];

function ProfileStatus({ skill }) {
  if (skill.profile_status === "in_profile") {
    const details = [PROFILE_LEVELS[skill.profile_proficiency_level]];
    if (typeof skill.profile_years_experience === "number") {
      details.push(`${new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 1 }).format(skill.profile_years_experience)} yıl deneyim`);
    }
    return <p className="analysis-profile-status">Profilinde kayıtlı{details.some(Boolean) ? ` · ${details.filter(Boolean).join(" · ")}` : ""}</p>;
  }
  if (skill.profile_status === "missing") {
    return <p className="analysis-profile-status analysis-profile-missing">Profilinde kayıtlı değil. Bu, beceriye sahip olmadığın anlamına gelmez.</p>;
  }
  return <p className="analysis-profile-status">Profil karşılaştırması bulunmuyor.</p>;
}

function SectionCoverage({ section, label }) {
  if (!section || section.total_count === 0 || section.match_percentage == null) {
    return <li><strong>{label}</strong><span>Bu bölümde katalogda tanınan beceri bulunamadı.</span></li>;
  }
  return (
    <li>
      <strong>{label}</strong>
      <span>{section.matched_count} / {section.total_count} · %{new Intl.NumberFormat("tr-TR", { maximumFractionDigits: 2 }).format(section.match_percentage)} profilde kayıtlı</span>
      {section.missing_skills?.length > 0 && <small>Profilinde kayıtlı olmayanlar: {section.missing_skills.join(", ")}</small>}
    </li>
  );
}

export default function JobAnalysisResults({ result }) {
  const metadata = result.metadata || {};
  const populatedMetadata = METADATA_FIELDS
    .map(([key, label]) => [key, label, metadata[key]])
    .filter(([, , item]) => item?.value);
  const profileMatch = result.profile_match;

  return (
    <section className="analysis-results" aria-live="polite">
      <h3>İlan özeti ve beceri karşılaştırması</h3>
      <p className="analysis-explanation" role="note">
        Bu sonuçlar katalogdaki ad ve alias eşleşmelerine dayanır; katalogda olmayan beceriler algılanmayabilir. Sonuçları ilan metniyle karşılaştır.
      </p>
      {result.role && (
        <p className="analysis-role">
          {result.role_source === "headline"
            ? "Başlık satırından algılanan rol:"
            : "Açıkça belirtilen rol:"} <strong>{result.role}</strong>
          {result.role_line_number && <small> · satır {result.role_line_number}</small>}
        </p>
      )}

      {populatedMetadata.length > 0 && (
        <section className="analysis-metadata" aria-label="İlanda açıkça belirtilen bilgiler">
          <h4>İlanda açıkça belirtilen bilgiler</h4>
          <p className="analysis-explanation">Yalnızca etiketli alanlar gösterilir; ilan metnindeki bilgileri doğrula.</p>
          <dl>
            {populatedMetadata.map(([key, label, item]) => (
              <div key={key}>
                <dt>{label}</dt>
                <dd>{item.value}<small>Satır {item.line_number}</small></dd>
              </div>
            ))}
          </dl>
        </section>
      )}

      {profileMatch && (
        <section className="analysis-profile-match" aria-label="Profil becerileriyle karşılaştırma">
          <h4>Profil becerilerinle karşılaştırma</h4>
          <p className="analysis-explanation">Yüzde, tanınan ilan becerilerinin kaçının profilinde kayıtlı olduğunu gösterir; iş için uygunluk veya başarı olasılığı değildir.</p>
          <ul>
            {SECTION_MATCHES.map(([key, label]) => (
              <SectionCoverage key={key} section={profileMatch[key]} label={label} />
            ))}
          </ul>
        </section>
      )}

      <h4>Bulunan beceriler</h4>
      {result.skills?.length ? (
        <ul className="analysis-skill-list">
          {result.skills.map((skill) => (
            <li key={skill.skill_id}>
              <strong>{skill.name}</strong>
              <span>{SKILL_CATEGORIES[skill.category] || skill.category || "Kategori belirtilmemiş"}</span>
              <ProfileStatus skill={skill} />
              {skill.occurrences.map((occurrence, index) => (
                <span className="analysis-occurrence" key={`${skill.skill_id}-${occurrence.line_number}-${index}`}>
                  <small>{occurrence.section === "required" ? "Zorunlu bölüm" : occurrence.section === "preferred" ? "Tercih bölümü" : "Belirtilmemiş bölüm"} · satır {occurrence.line_number}</small>
                  {occurrence.matched_text && <small>İlanda görülen ifade: “{occurrence.matched_text}”</small>}
                </span>
              ))}
            </li>
          ))}
        </ul>
      ) : <p>Katalogda tanınan beceri eşleşmesi bulunamadı.</p>}
    </section>
  );
}
